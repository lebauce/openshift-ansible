# openshift_storage_cinder

This role is useful to create and export Openstack Cinder volumes for openshift
persistent volumes. It does so by :

* issuing requests to the Openstack APIs to create volumes
* attach them to the virtual machine the playbook is executed on
* format it using ext4
* set the proper rights on the filesystem
* register persistent volume
* register persistent volume claims to be used by Openshift

## Requirements

* Openshift must be configured to use the Openstack cloud provider
  (see [https://docs.openshift.com/enterprise/3.1/install_config/configuring_openstack.html])

## Role Variables

```
# Openstack authentication URL
os_auth_url: "{{ lookup('env', 'OS_AUTH_URL') }}"

# Openstack username
os_username: "{{ lookup('env', 'OS_USERNAME') }}"

# Openstack password
os_password: "{{ lookup('env', 'OS_PASSWORD') }}"

# Openstack tenant name
os_tenant_name: "{{ lookup('env', 'OS_TENANT_NAME') }}"

# Openstack region
os_region: "{{ lookup('env', 'OS_REGION_NAME') }}"

# Number of volumes to create
osc_number_of_volumes: 1

# Index of the first volume to create
osc_volume_num_start: 1

# Prefix to use for the volume name
osc_volume_prefix: openshift-volume-

# Size in GB of the volumes to create
osc_volume_size: 1
```

## Dependencies

None

## Example Playbook

With this playbook, 2 5Gig Cinder volumes are created, named openshift-volume-5g0003
and openshift-volume-5g0004. 2 persistent volume with the same name will be created,
and 2 persistent volume claim (prefixed with 'claim-') will be created.

    - hosts: localhost
      gather_facts: no
      roles:
        - role: openshift_storage_cinder
          os_auth_url: http://1.2.3.4:5000/v2
          os_username: user1
          os_password: passw0rd
          os_tenant_name: project1
          os_region: RegionOne
          osc_volume_size: 5
          osc_number_of_volumes: 2
          osc_volume_num_start: 3
          osc_volume_prefix: openshift-volume-

## Full example

* Create an ansible playbook, say `setupcinder.yaml`:
    ```
    - hosts: all
      gather_facts: no
        - role: openshift_storage_cinder
          os_auth_url: http://1.2.3.4:5000/v2
          os_username: user1
          os_password: passw0rd
          os_tenant_name: project1
          os_region: RegionOne
          osc_volume_size: 5
          osc_number_of_volumes: 2
          osc_volume_num_start: 3
          osc_volume_prefix: openshift-volume-
    ```

* Run the playbook:
    ```
    ansible-playbook -i "localhost," setupcinder.yml
    ```

## License

Apache 2.0
