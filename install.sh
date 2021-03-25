
#!/bin/sh

if [ $# -ne 1 ]; then
    echo "Usage: $0 <nao_robot_ip>"
    exit 1
fi

qipkg make-package deep_nao.pml
robot=$1
rsync -arv deep_nao-1.0.0.pkg nao@$robot:
ssh nao@$robot qicli call PackageManager.remove deep_nao
ssh nao@$robot qicli call PackageManager.install /home/nao/deep_nao-1.0.0.pkg
