# Phoenix Bios Dump

レガシーなPhoenix BIOSをモジュール分割するプログラムです。
2つの機能があります。

* モジュールダンプ：分割したモジュールをファイルへ保存します
* マイクロコードアップデート：BIOS内のUPDATE0モジュールのmicrocodeを差し替えます

## Usage

    python3 PhoenixBiosDump biosfile [microcodefile...] [-d]

### options

* microcodefile マイクロコードのファイルを指定します。複数指定可能です。
* -d モジュールダンプを実行します

### Examples

    python3 PhoenixBiosDump BIOS2M.WPH 06-1e-05 06-25-02 06-25-05

BIOS2M.WPHファイルのマイクロコードを3つ差し替えます。

    python3 PhoenixBiosDump BIOS2M.WPH -d

BIOS2M.WPHファイルのモジュールを分割してファイルへ保存します。

## FYI

参考情報として、マイクロコードは[intel/Intel-Linux-Processor-Microcode-Data-Files](https://github.com/intel/Intel-Linux-Processor-Microcode-Data-Files)
にて探すことができます。

## Authors

* marbocub - Initial work

## License

This project is licensed under the MIT License -
see the [LICENSE](LICENSE) file for details.
