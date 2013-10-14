import cloudsigma
import os
import stat

metadata = cloudsigma.metadata.GetServerMetadata().get()
ssh_key = metadata['meta']['ssh_public_key']

# Define paths
home = os.path.expanduser("~")
ssh_path = os.path.join(home, '.ssh')
authorized_keys = os.path.join(ssh_path, 'authorized_keys')


def get_permission(path):
    return oct(os.stat(ssh_path)[stat.ST_MODE])[-4:]

if not os.path.isdir(ssh_path):
    print 'Creating folder %s' % ssh_path
    os.makedirs(ssh_path)

if get_permission(ssh_path) != 0700:
    print 'Setting permission for %s' % ssh_path
    os.chmod(ssh_path, 0700)

# We'll have to assume that there might be other keys installed.
# We could do something fancy, like checking if the key is installed already,
# but in order to keep things simple, we'll simply append the key.
with open(authorized_keys, 'a') as auth_file:
    auth_file.write(ssh_key + '\n')

if get_permission(authorized_keys) != 0600:
    print 'Setting permission for %s' % authorized_keys
    os.chmod(authorized_keys, 0600)
