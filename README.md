
# mugisync

Continously syncronizes local directory with another local or shared directory (poor person's syncthing) or remote directory over ssh (poor person's one-way sshfs).

## Installing

Mugisync can be installed via pip as follows:

```bash
pip install mugisync
```

## Using

```bash
mugisync /path/to/src /path/to/dst -i "*.cpp" -e "moc_*" ".git"
mugisync /src/path/libfoo.dll /dst/path
mugisync /path/to/src root@192.168.0.1:/root/src
```

## Author

Stanislav Doronin <mugisbrows@gmail.com>

## License

Mugisync is distributed under the terms of MIT license, check `LICENSE` file.
