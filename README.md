# offline_file_scan_custom(正则匹配本地文件敏感信息扫描python程序)


**一、使用root用户安装python依赖**
```
yum install -y gcc make openssl-devel libffi-devel zlib-devel bzip2-devel readline-devel sqlite-devel ncurses-devel tk-devel xz-devel  libdb-devel gdbm-devel libuuid-devel libnsl2-devel readline-devel  python3-devel
```
+ 联网机器下载依赖离线包
```
mkdir python3.12_depend
yum reinstall -y --downloadonly --downloaddir=./python3.12_depend/ gcc make openssl-devel libffi-devel zlib-devel bzip2-devel readline-devel sqlite-devel ncurses-devel tk-devel xz-devel  libdb-devel gdbm-devel libuuid-devel libnsl2-devel readline-devel  python3-devel
```
+ 离线机器安装依赖包
```
rpm -ivh ./python3.12_depend/*.rpm
```

**二、编译安装python3.12.8**

1. root用户编译安装

+ altinstall 会忽略 --prefix，默认安装到 /usr/local，需改用 make install
```
./configure --enable-optimizations --enable-shared --with-openssl=/usr --prefix=/usr/ && make -j$(nproc) && make altinstall
./configure --enable-optimizations --enable-shared --with-openssl=/usr --prefix=/usr/local/python3.12 && make -j$(nproc) && make install
```
+ 配置环境变量
```
vi /etc/profile
export PATH=/usr/local/python3.12/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/python3.12/lib:$LD_LIBRARY_PATH
```
2. 普通用户编译安装
```
./configure --enable-optimizations --enable-shared --with-openssl=/usr --prefix=/home/isearch/python3.12 && make -j$(nproc) && make install
```
+ 配置环境变量
```
vi ~/.bashrc
export PATH=/home/isearch/python3.12/bin:$PATH
export LD_LIBRARY_PATH=/home/isearch/python3.12/lib:$LD_LIBRARY_PATH
```

**三、运行程序**

+ 创建venv虚拟环境
```
python3.12 -m venv venv_linux
```
+ 激活venv
```
source ./venv_linux/bin/activate
```
+ 在线安装requirements.txt依赖
```
pip3.12 install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ 
```
+ 在联网的环境中，可以使用以下命令将requirements.txt文件中列出的所有依赖包下载到指定目录：
```
mkdir requirements
pip3.12 download -d requirements -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ 
```
+ 离线环境中，安装下载的依赖包：
```
pip3.12 install --no-index --find-links=requirements -r requirements.txt
```
+ 运行程序
```
python3.12 offline_file_scan_custom_pack.py
```
