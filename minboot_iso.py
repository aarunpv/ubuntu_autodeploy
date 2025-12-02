import os
import shutil
import tempfile
import pycdlib
import re
from pyfatfs.PyFatFS import PyFatFS, PyFat

'''
Creates a UEFI-bootable Ubuntu autoinstall ISO using NoCloud data source.


'''

# ---------------- CONFIG ----------------
UBUNTU_ISO_PATH = "/iso/ubuntu-24.04.3-live-server-amd64.iso"
VM_NAME = "vm01"
AUTOINSTALL_PATH = f"/iso/{VM_NAME}/autoinstall"   # contains user-data, meta-data, etc. directly
OUTPUT_ISO_PATH = f"/iso/{VM_NAME}/bootstrap.iso"

WORK_DIR = tempfile.mkdtemp()
CASPER_DIR = os.path.join(WORK_DIR, "casper")
EFI_DIR = os.path.join(WORK_DIR, "EFI")
os.makedirs(CASPER_DIR, exist_ok=True)
os.makedirs(EFI_DIR, exist_ok=True)

# ---------------- HELPERS ----------------
def extract_first(iso_obj, candidates, dest):
    for c in candidates:
        try:
            with open(dest, "wb") as f:
                iso_obj.get_file_from_iso_fp(outfp=f, iso_path=c)
            print(f"Extracted {c} → {dest}")
            return
        except Exception:
            continue
    raise RuntimeError(f"None of {candidates} found in ISO!")

def iso9660_name(name):
    base = os.path.splitext(name)[0]
    base = re.sub(r"[^A-Z0-9_]", "_", base.upper())
    return base

def add_dir_safe(newiso, iso_dir_path):
    if not iso_dir_path.startswith("/"):
        iso_dir_path = "/" + iso_dir_path
    try:
        rr_name = iso_dir_path.rsplit("/",-1)[-1].lower()
        print(rr_name)
        newiso.add_directory(iso_path=iso_dir_path,rr_name=rr_name)
        print(f"[DIR] Added {iso_dir_path}")
    except pycdlib.pycdlibexception.PyCdlibException:
        pass

def add_file_safe(newiso, disk_path, iso_file_path,rr_name):
    try:
        newiso.add_file(disk_path, iso_file_path,rr_name=rr_name)
        print(f"[FILE] Added {iso_file_path}")
    except Exception:
        print(f"[ADD_FILE ERROR] ISO path: {iso_file_path}  DISK path: {disk_path}")
        raise

def create_efi_fat_image(efi_image_path, bootx64_path, grubx64_path, size_mb):
    size = size_mb * 1024 * 1024
    with open(efi_image_path, "wb") as f:
        f.truncate(size)

    pf = PyFat()
    pf.encoding = "utf-8"
    pf.mkfs(filename=efi_image_path, fat_type=16)
    pf.open_fs(efi_image_path)
    pf.close()

    pf = PyFatFS(filename=efi_image_path)
    pf.makedirs("/EFI/BOOT")

    with open(bootx64_path, "rb") as f:
        pf.writefile("/EFI/BOOT/BOOTX64.EFI", f)

    with open(grubx64_path, "rb") as f:
        pf.writefile("/EFI/BOOT/grubx64.efi", f)

    pf.close()

# ---------------- MAIN ----------------
try:
    print("Opening Ubuntu ISO...")
    iso = pycdlib.PyCdlib()
    iso.open(UBUNTU_ISO_PATH)

    kernel_candidates = ["/CASPER/VMLINUZ.;1", "/CASPER/HWE_VMLINUZ.;1"]
    initrd_candidates = ["/CASPER/INITRD.;1", "/CASPER/HWE_INITRD.;1"]
    boot_efi_candidates = ["/EFI/BOOT/BOOTX64.EFI;1"]
    grub_efi_candidates = ["/EFI/BOOT/GRUBX64.EFI;1"]

    extract_first(iso, kernel_candidates, os.path.join(CASPER_DIR, "vmlinuz"))
    extract_first(iso, initrd_candidates, os.path.join(CASPER_DIR, "initrd"))
    extract_first(iso, boot_efi_candidates, os.path.join(EFI_DIR, "BOOTX64.EFI"))
    extract_first(iso, grub_efi_candidates, os.path.join(EFI_DIR, "grubx64.efi"))

    print(f"Creating UEFI bootable ISO at {OUTPUT_ISO_PATH}")
    newiso = pycdlib.PyCdlib()
    # Volume label (ISO9660 volume ID) for NoCloud
    newiso.new(interchange_level=3, vol_ident="CIDATA",rock_ridge="1.09")

    # Pre-create top-level dirs
    for d in ["/EFI", "/EFI/BOOT", "/CASPER", "/BOOT", "/BOOT/GRUB"]:
        add_dir_safe(newiso, d)
    # Kernel + initrd
    add_file_safe(newiso, os.path.join(CASPER_DIR, "vmlinuz"), "/CASPER/VMLINUZ;1","vmlinuz")
    add_file_safe(newiso, os.path.join(CASPER_DIR, "initrd"), "/CASPER/INITRD;1","initrd")
    add_file_safe(newiso,os.path.join(AUTOINSTALL_PATH, "user-data"), "/USER_DATA;1","user-data")
    add_file_safe(newiso,os.path.join(AUTOINSTALL_PATH, "meta-data"), "/META_DATA;1","meta-data")



    # GRUB config
    grubcfg = f"""
set timeout=0
set root=cd1

menuentry "Ubuntu Auto Install {VM_NAME}" {{
    linux /casper/hwe-vmlinuz quiet autoinstall ds=nocloud ---
    initrd /casper/hwe-initrd
}}
""".strip()
    GRUB_CFG_PATH = os.path.join(WORK_DIR, "grub.cfg")
    with open(GRUB_CFG_PATH, "w") as f:
        f.write(grubcfg)

    add_file_safe(newiso, GRUB_CFG_PATH, "/BOOT/GRUB/GRUB.CFG","grub.cfg")

    EFI_IMG_PATH = os.path.join(WORK_DIR, "efiboot.img")
    create_efi_fat_image(
        EFI_IMG_PATH,
        os.path.join(EFI_DIR, "BOOTX64.EFI"),
        os.path.join(EFI_DIR, "grubx64.efi"),
        16,
    )

    add_file_safe(newiso, EFI_IMG_PATH, "/EFI/BOOT/EFIBOOT.IMG;1","efiboot.img")

    newiso.add_eltorito(
        bootfile_path="/EFI/BOOT/EFIBOOT.IMG;1",
        media_name="noemul",
        platform_id=0xEF,
        bootable=True,
        efi=True,
        bootcatfile="/BOOT;1",
    )

    newiso.write(OUTPUT_ISO_PATH)
    newiso.close()
    print("UEFI Bootable ISO completed:", OUTPUT_ISO_PATH)

except Exception as e:
    print("ERROR:", e)

finally:
    shutil.rmtree(WORK_DIR, ignore_errors=True)
