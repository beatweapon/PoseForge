# PoseForge

オフラインで動く、AI向け3Dポーズ参考画像生成の実験ツールです。

## 現在の到達点

MVP 0.1 は **簡易的な人体・手の形状プロキシ** とカードを Blender のPythonで生成し、同じシーンを正面・背面・側面・斜め・手元拡大からレンダリングします。**実際の人体リグ・IK・衝突検出はまだありません。** 指先の設計上の接触点だけ数値検証します。写実的な人体や自然な握りを保証するものではありません。

## 必要環境

- Windows 11 / Python 3.10+（標準ライブラリのみ）
- Blender 4.2+（PATHに `blender`、または `--blender` で実行ファイルを指定）

## 実行例（PowerShell）

```powershell
py -m poseforge.cli validate examples/card_pinch.json
py -m poseforge.cli render examples/card_pinch.json --blender "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
py -m unittest discover -s tests -v
```

Blender が PATH にある場合、`--blender` は省略できます。出力先はJSONの `output`（設定ファイルのディレクトリを基準とする相対パス）です。既存出力は上書きされます。

出力: `front.png`、`back.png`、`left.png`、`right.png`、`three_quarter.png`、`hand_closeup.png`、`report.json`。背景透過RGBA、正投影。カードの青い面を表、オレンジ面を裏として表示します。

## アーキテクチャ

- `poseforge/schema.py`: オフラインJSON検証（Blender不要）
- `poseforge/cli.py`: Blenderのバックグラウンド実行
- `poseforge/blender_scene.py`: Blender内で簡易ジオメトリを生成し一括撮影
- `examples/card_pinch.json`: 意味的アクションのサンプル

## 明確な制限

- 人体は関節を持つ実モデルでなく、カプセル/球状の簡易プロキシです。手首・腕・指の動作の自由度は限定的です。
- `pinch` だけを受理し、カードと二つの指の接触点は計算済みの配置です。IKは未実装。
- 検証は点とカード表面の距離の測定であり、実際のメッシュ衝突・貫通判定ではありません。
- Blender実機でのレンダリング検証は利用環境ごとに実施してください。ソースをGitHubへ反映したことは、実機検証の成功を意味しません。
- 実行時に外部ネットワークAPIは呼びません。BlenderとPythonのインストールにはネット接続が必要な場合があります。

## 次の段階

ライセンスの明確な五指リグ付き人体モデルを導入し、IK・接触/貫通検出・数値誤差レポートを実際のモデルに適用します。MCP等のAI連携はコアCLIと切り離して追加します。
