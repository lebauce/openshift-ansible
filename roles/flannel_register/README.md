Role Name
=========

Register flannel configuration into etcd

Requirements
------------

This role assumes it's being deployed on a RHEL/Fedora based host with package
named 'flannel' available via yum, in version superior to 0.3.

Role Variables
--------------

TODO

Dependencies
------------

openshift_facts

Example Playbook
----------------

    - hosts: openshift_master
      roles:
         - { flannel_register }

License
-------

Apache License, Version 2.0

Author Information
------------------

Sylvain Baubeau <sbaubeau@redhat.com>
