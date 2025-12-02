from pyVmomi import vim
from pyVim.connect import SmartConnect,Disconnect


def get_obj(content, vimtypes, name):
    cv = content.viewManager.CreateContainerView(content.rootFolder, vimtypes, True)
    for o in cv.view:
        if o.name == name:
            return o
    return None


def build_cdrom_spec(controller, unit_number, datastore, iso_rel_path, key):
    cd = vim.vm.device.VirtualCdrom()
    cd.key = key                    # unique per device
    cd.controllerKey = controller.key
    cd.unitNumber = unit_number

    backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
    backing.datastore = datastore
    backing.fileName = f"[{datastore.name}] {iso_rel_path}"
    cd.backing = backing

    connect = vim.vm.device.VirtualDevice.ConnectInfo()
    connect.startConnected = True
    connect.connected = True
    connect.allowGuestControl = True
    cd.connectable = connect

    spec = vim.vm.device.VirtualDeviceSpec()
    spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    spec.device = cd
    return spec


def configure_vm_cdroms_and_boot(
    si,
    vm_name,
    datastore_name,
    iso1_rel,   # for CD-ROM 1
    iso2_rel,   # for CD-ROM 2
):
    content = si.RetrieveContent()
    vm = get_obj(content, [vim.VirtualMachine], vm_name)
    if not vm:
        raise RuntimeError("VM not found")

    ds = get_obj(content, [vim.Datastore], datastore_name)
    if not ds:
        raise RuntimeError("Datastore not found")

    # 1) remove all existing CD/DVD devices
    device_changes = []
    for dev in vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualCdrom):
            rm = vim.vm.device.VirtualDeviceSpec()
            rm.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
            rm.device = dev
            device_changes.append(rm)

    # 2) find first IDE controller
    ide = next(
        d for d in vm.config.hardware.device
        if isinstance(d, vim.vm.device.VirtualIDEController)
    )

    # 3) add CD-ROM1 on IDE(0:0) with iso1, CD-ROM2 on IDE(0:1) with iso2
    cd1_spec = build_cdrom_spec(
        controller=ide,
        unit_number=0,
        datastore=ds,
        iso_rel_path=iso1_rel,
        key=-101,
    )
    cd2_spec = build_cdrom_spec(
        controller=ide,
        unit_number=1,
        datastore=ds,
        iso_rel_path=iso2_rel,
        key=-102,
    )
    device_changes.extend([cd1_spec, cd2_spec])

    # 4) set boot order: CD-ROM first, then disk
    boot_cd = vim.vm.BootOptions.BootableCdromDevice()
    boot_opts = vim.vm.BootOptions(bootOrder=[boot_cd])


    cfg = vim.vm.ConfigSpec()
    cfg.deviceChange = device_changes
    cfg.bootOptions = boot_opts

    return vm.ReconfigVM_Task(cfg)


if __name__ == "__main__":
    si = SmartConnect(
<<<<<<< HEAD
            host="VCENTER_IP/FQDN",
            user="USERNAME",
            pwd="PASSWORD", 
=======
            host="VCENTER_IP/HOSTNAME",
            user="VC_USERNAME",
            pwd="VC_PASSWORD", 
>>>>>>> 4da4c932c4f5e637c7b536e7211012b522f826ab
            disableSslCertValidation=True)
    task = configure_vm_cdroms_and_boot(
        si =si,
        vm_name="test",
        datastore_name="iso",
        iso1_rel="vm01/bootstrap.iso",
        iso2_rel="ubuntu-24.04.3-live-server-amd64.iso"
    )
