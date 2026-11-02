# MPFBのコマンドライン導入

Blender 5.2.3 LTSを推奨します。MPFB 2.0.18はBlender 4.2以降をサポートしています（公式Blender Extensions）。MPFBはGPL-3.0以降で、生成した標準人体アセットのライセンスとは別です。

1. 初回のみ拡張機能をネットワークから導入します。
2. 以後の人体生成はローカルのBlender + MPFBだけで実行します。

```powershell
git pull
py -m poseforge.cli setup-mpfb --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
py -m poseforge.cli create-human assets/human.blend --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
py -m poseforge.cli inspect-model assets/human.blend --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

`setup-mpfb` は公式の `blender --command extension install -s -e mpfb` を呼びます。オンライン拡張リポジトリが使えない環境では失敗する場合があります。

`create-human` はMPFBの `HumanService.create_human()` と `add_builtin_rig(..., "default")` を呼び、ボーンに親指と人差し指が確認できない場合には成功としません。出力は `assets/human.blend` とメタ情報JSONです。APIまたは初期アセットがインストール環境と一致しない場合はエラーが出ます。その場合はログをもとに修正します。

**未検証:** Blender 5.2.3でのこの自動生成フローはまだ実機テストしていません。モデル生成に成功してもカードをつまむポーズは未実装で、従来の `render` は試作0の簡易形状を使用します。

公式資料:
- https://extensions.blender.org/add-ons/mpfb/versions/
- https://docs.blender.org/manual/en/5.2/advanced/command_line/extension_arguments.html
- https://github.com/makehumancommunity/mpfb2
