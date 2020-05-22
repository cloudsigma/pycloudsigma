from cloudsigma.bulk import DrivesBulk


def drives_create(id_prefix, count):
    count = int(count)

    stress_drives = DrivesBulk(id_prefix=id_prefix,
                               )
    stress_drives.create(count)


def drives_clone(id_prefix, count, source_drive):
    count = int(count)

    stress_drives = DrivesBulk(id_prefix=id_prefix,
                               )
    stress_drives.clone(count, source_drive)


def drives_clone_all(id_prefix, count):
    stress_drives = DrivesBulk(id_prefix=id_prefix)
    res = stress_drives.clone_all(count)
    print(res)


def drives_list(id_prefix):
    stress_drives = DrivesBulk(id_prefix=id_prefix,
                               )
    ds = stress_drives.get_list()
    print(ds)


def _drives_get_by_uuids(id_prefix, uuids):
    stress_drives = DrivesBulk(id_prefix=id_prefix,
                               )
    ds = stress_drives.get_by_uuids(uuids)
    print(ds)


def drives_detail(id_prefix):
    stress_drives = DrivesBulk(id_prefix=id_prefix,
                               )
    ds = stress_drives.get_detail()
    print(ds)


def drives_wipe(id_prefix):
    stress_drives = DrivesBulk(id_prefix=id_prefix,
                               )
    stress_drives.wipe()


def drives_number(id_prefix):
    stress_drives = DrivesBulk(id_prefix=id_prefix,
                               )
    ds = stress_drives.get_list()
    print("Number of DRIVES: %r" % len(ds))
