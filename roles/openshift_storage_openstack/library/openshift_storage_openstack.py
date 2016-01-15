#!/usr/bin/python
# pylint: disable=maybe-no-member, access-member-before-definition
# pylint: disable=broad-except, bare-except

"""Ansible module to manage Openstack volumes to be used by Openshift"""

DOCUMENTATION = '''
---
module: openshift_storage_openstack
short_description: Create Openstack volumes for Openshift
author: Sylvain Baubeau
requirements: [ python-novaclient ]
'''
EXAMPLES = '''
'''

import time
import os
import subprocess
import tempfile
import urllib2
import json
import yaml

from novaclient.client import Client


class VolumeManager(object):
    """ Manage Openstack volume """

    metadata_url = 'http://169.254.169.254/openstack/latest/meta_data.json'

    def __init__(self, module):
        self.module = module
        self.__dict__.update(module.params.copy())

        if not self.server:
            response = urllib2.urlopen(self.metadata_url)
            self.server = json.load(response)['uuid']

        self.client = self.authenticate()
        volume = self.create_volume()
        attachment, device = self.attach_volume(volume)
        self.prepare_volume(device)
        self.detach_volume(volume, attachment)
        self.create_persistent_volume(volume)
        self.create_persistent_volume_claim()

    def authenticate(self):
        """ Authenticate against the Openstack Nova API """

        try:
            return Client(self.api_version,
                          username=self.username,
                          project_id=self.tenant,
                          api_key=self.password,
                          auth_url=self.auth_url,
                          endpoint_type=self.endpoint_type,
                          http_log_debug=True)
        except Exception, ex:
            self.module.fail_json(msg="Failed to authenticate: %s" % ex)

    def create_volume(self):
        """ Create a volume and wait for it to be available """

        conf = {'display_name': self.volume_name,
                'size': self.volume_size}

        if self.volume_type:
            conf['volume_type'] = self.volume_type

        if self.availability_zone:
            conf['availability_zone'] = self.availability_zone

        try:
            volume = self.client.volumes.create(**conf)
        except Exception, ex:
            self.module.fail_json(msg="Failed to create volume: %s" % ex)

        # Wait for the volume to be available
        timer = 0
        while volume.status != "available":
            if timer >= self.timeout:
                err = "Timeout when waiting for volume to be available"
                self.module.fail_json(msg=err)

            time.sleep(1)
            timer += 1
            volume.get()

        return volume

    def attach_volume(self, volume):
        """ Attach the volume to the server and both the attachment
            and the corresponding device """

        try:
            attachment = self.client.volumes.create_server_volume(self.server,
                                                                  volume.id,
                                                                  "")
        except Exception, ex:
            self.module.fail_json(msg="Failed to attach volume: %s" % ex)

        # Wait for the device to show up
        timer = 0
        device = ""
        while not device:
            for dev in os.listdir("/dev/disk/by-id"):
                if volume.id[:8] in dev:
                    device = "/dev/disk/by-id/" + dev
                    break

            if device:
                break

            if timer >= self.timeout:
                err = "Timeout when waiting for volume to be attached"
                self.module.fail_json(msg=err)

            time.sleep(1)
            timer += 1

        return attachment, device

    def prepare_volume(self, device):
        """ Format the volume, mount it, set its mode to 777
            then unmount it """

        tmpdir = tempfile.mkdtemp()

        try:
            subprocess.call(["mkfs." + self.filesystem, device])
            subprocess.call(["mount", device, tmpdir])
            subprocess.call(["chmod", "-R", "777", tmpdir])
            subprocess.call(["umount", tmpdir])
        except Exception, ex:
            self.module.fail_json(msg="Failed to prepare volume %s" % ex)

        os.rmdir(tmpdir)

    def detach_volume(self, volume, attachment):
        """ Detach the volume from the server """

        # In some cases, the volume status hasn't been updated yet
        # so trying to detach it throws an error. To avoid it, we wait
        # for the status to have been updated
        timer = 0
        while True:
            volume = self.client.volumes.get(volume.id)
            if volume.status == "in-use":
                break

            if timer >= self.timeout:
                break

            time.sleep(1)
            timer += 1

        # Detach the volume
        try:
            self.client.volumes.delete_server_volume(self.server,
                                                     attachment.id)
        except Exception, ex:
            self.module.fail_json("Failed to detach volume: %s" % ex)

        # Wait for the volume to be detached
        timer = 0
        while True:
            try:
                self.client.volumes.get_server_volume(self.server,
                                                      attachment.id)
            except:
                break

            if timer >= self.timeout:
                err = "Timeout when waiting for volume to be detached"
                self.module.fail_json(msg=err)

            time.sleep(1)
            timer += 1

    def create_persistent_volume(self, volume):
        """ Create a persistent volume of the 'cinder' type """

        pvdef = {
            "apiVersion": "v1",
            "kind": "PersistentVolume",
            "metadata": {
                "name": self.volume_name
            },
            "spec": {
                "capacity": {
                    "storage": "%dGi" % self.volume_size
                },
                "accessModes": self.access_modes,
                "cinder": {
                    "fsType": self.filesystem,
                    "volumeID": str(volume.id)
                }
            }
        }

        pvfile = tempfile.mkstemp()[1]
        yaml.dump(pvdef, open(pvfile, "w"))
        try:
            subprocess.call(["oc", "create", "-f", pvfile])
        except:
            self.module.fail_json(msg="Failed to register persistent volume")
        os.unlink(pvfile)

    def create_persistent_volume_claim(self):
        """ Create a persistent volume claim """

        pvcdef = {
            "kind": "PersistentVolumeClaim",
            "apiVersion": "v1",
            "metadata": {
                "name": "claim-" + self.volume_name,
            },
            "spec": {
                "accessModes": self.access_modes,
                "resources": {
                    "requests": {
                        "storage": "%dGi" % self.volume_size
                    }
                }
            }
        }

        pvcfile = tempfile.mkstemp()[1]
        yaml.dump(pvcdef, open(pvcfile, "w"))
        try:
            subprocess.call(["oc", "create", "-f", pvcfile])
        except:
            err = "Failed to register persistent volume claim"
            self.module.fail_json(msg=err)
        os.unlink(pvcfile)


def main():
    """ main """
    module = AnsibleModule(
        argument_spec=dict(
            auth_url=dict(required=True),
            username=dict(required=True),
            password=dict(required=True),
            tenant=dict(required=True),
            endpoint_type=dict(required=False, default="publicURL"),
            endpoint_url=dict(required=False, default=None),
            api_version=dict(required=False, default="2"),
            volume_name=dict(required=False, default="cinder-volume"),
            volume_size=dict(required=False, default=5),
            volume_type=dict(required=False, default=None),
            filesystem=dict(required=False, default="ext4"),
            server=dict(required=False, default=None),
            availability_zone=dict(required=False, default=None),
            timeout=dict(required=False, default=30),
            access_modes=dict(required=False, default=["ReadWriteOnce"]),
        ),
        supports_check_mode=False,
        add_file_common_args=False,
    )

    VolumeManager(module)
    return module.exit_json(changed=True)

# ignore pylint errors related to the module_utils import
# pylint: disable=redefined-builtin, unused-wildcard-import, wildcard-import
# import module snippets
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
