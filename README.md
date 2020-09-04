# Dynamic inventory script for working with Yandex.Cloud
## Config-file
The simplest config file might look like this:
```yaml
keyFile: key.json
folderId: # paste your folder-id here
tags:
  tagName:
  tagName1:
```
It will return an inventory:
```json
{
    "tagName": {
        "hosts": ["host's ip1", "host's ip2"]  
    },
    "tagName1": {
        "hosts": ["host's ip1", "host's ip2"]  
    }
}
```
* `keyFile`  
Defines a path to the service-account key file.

* `tags`  
Defines which instances must be collected for the inventory. It contains tags of the instances.  
For each of the tags an alias can be defined by setting up a `hostsName` value.  
E.g.:
```yaml
tags:
  tagName:
    hostsName: my-app
  tagName1:
```
will return
```json
{
    "my-app": {
        "hosts": ["host's ip1", "host's ip2"]  
    },
    "tagName1": {
        "hosts": ["host's ip1", "host's ip2"]  
    }
}
```
### Hosts Variables
It's also possible to set some host's variables. It might be useful when them's values are dynamic as well.
* `vars`  
It's the options which allows to set host's variables. It has who options:  
    * `value`  
    allows to set a static value
    * `hosts`
    allows to set list of hosts by instance's tags. It's also possible to to set just one host address by array-like indexing.  
E.g.  
```yaml
tags:
  tagName:
    hostsName: my-app
  tagName1:
    vars:
      myVar:
        hosts: tagName[0]
```
will return
```json
{
    "my-app": {
        "hosts": ["host's ip1", "host's ip2"]  
    },
    "tagName1": {
        "hosts": ["host's ip1", "host's ip2"],  
        "vars": {
            "myVar": "host's ip1"
        }
    }
}
```
since `myVar` was defined with index `tagName[0]` it's not a list, but single(first) host address.