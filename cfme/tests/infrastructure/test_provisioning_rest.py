import fauxfactory
import pytest

from cfme import test_requirements
from cfme.infrastructure.provider.rhevm import RHEVMProvider
from cfme.infrastructure.provider.virtualcenter import VMwareProvider
from utils.wait import wait_for
from utils import testgen


pytestmark = [test_requirements.provision]

pytest_generate_tests = testgen.generate([VMwareProvider, RHEVMProvider], scope="module")


@pytest.fixture(scope="module")
def provision_data(rest_api_modscope, provider, small_template_modscope):
    templates = rest_api_modscope.collections.templates.find_by(name=small_template_modscope)
    for template in templates:
        try:
            ems_id = template.ems_id
        except AttributeError:
            continue
        if ems_id == provider.id:
            guid = template.guid
            break
    else:
        raise Exception("No such template {} on provider!".format(small_template_modscope))
    result = {
        "version": "1.1",
        "template_fields": {
            "guid": guid
        },
        "vm_fields": {
            "number_of_cpus": 1,
            "vm_name": "test_rest_prov_{}".format(fauxfactory.gen_alphanumeric()),
            "vm_memory": "2048",
            "vlan": provider.data["provisioning"]["vlan"],
        },
        "requester": {
            "user_name": "admin",
            "owner_first_name": "John",
            "owner_last_name": "Doe",
            "owner_email": "jdoe@sample.com",
            "auto_approve": True
        },
        "tags": {
            "network_location": "Internal",
            "cc": "001"
        },
        "additional_values": {
            "request_id": "1001"
        },
        "ems_custom_attributes": {},
        "miq_custom_attributes": {}
    }
    if provider.one_of(RHEVMProvider):
        result["vm_fields"]["provision_type"] = "native_clone"
    return result


# Here also available the ability to create multiple provision request, but used the save
# href and method, so it doesn't make any sense actually
@pytest.mark.tier(2)
@pytest.mark.meta(server_roles="+automate")
@pytest.mark.usefixtures("setup_provider")
def test_provision(request, provision_data, provider, rest_api):
    """Tests provision via REST API.
    Prerequisities:
        * Have a provider set up with templates suitable for provisioning.
    Steps:
        * POST /api/provision_requests (method ``create``) the JSON with provisioning data. The
            request is returned.
        * Query the request by its id until the state turns to ``finished`` or ``provisioned``.
    Metadata:
        test_flag: rest, provision
    """

    vm_name = provision_data["vm_fields"]["vm_name"]
    request.addfinalizer(
        lambda: provider.mgmt.delete_vm(vm_name) if provider.mgmt.does_vm_exist(
            vm_name) else None)
    response = rest_api.collections.provision_requests.action.create(**provision_data)
    assert rest_api.response.status_code == 200
    provision_request = response[0]

    def _finished():
        provision_request.reload()
        if provision_request.status.lower() in {"error"}:
            pytest.fail("Error when provisioning: `{}`".format(provision_request.message))
        return provision_request.request_state.lower() in {"finished", "provisioned"}

    wait_for(_finished, num_sec=600, delay=5, message="REST provisioning finishes")
    assert provider.mgmt.does_vm_exist(vm_name), "The VM {} does not exist!".format(vm_name)
