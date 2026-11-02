# PoseForge

Blender 5.2.3 + Pythonで動く、ローカル完結型の**全身ポーズ参考資料生成ツール**です。初期ユースケースはカードをつまむ右手ですが、設計は全身Actorを対象とします。

## 現在できること

- MPFBでリグ付き全身人体を生成（`create-human`）
- 骨階層の解析（`inspect-model`、MPFBのfinger番号を分類）
- **実際の全身モデル**を同一シーンから6視点レンダリング（`render-human`）
- **実験的**に右腕・指を動かしてカードを置くプレビュー（`render-pinch`）

**重要:** `render-pinch` はまだ正しいつまみではありません。指とカードの接触点、IK、衝突・貫通判定は未実装です。今後これを検証・改良します。以前の棒人間試作は削除しました。

## 初期セットアップ（Windows PowerShell）

```powershell
py -m poseforge.cli setup-mpfb --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
py -m poseforge.cli create-human assets/human.blend --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
py -m poseforge.cli inspect-model assets/human.blend --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

## レンダリング

```powershell
py -m unittest discover -s tests -v
py -m poseforge.cli validate examples/human_neutral.json
py -m poseforge.cli render-human examples/human_neutral.json --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
py -m poseforge.cli render-pinch examples/human_card_pinch.json --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

出力は `output/human_neutral` と `output/human_card_pinch`（生成物・ローカル人体モデルはGit管理対象外）。レンダリング時のインターネット接続は不要です。

## 構成

- `poseforge/rig.py`: モデル依存の骨名アダプター
- `poseforge/schema.py`: JSON検証
- `poseforge/cli.py`: Blenderバックグラウンド起動
- `poseforge/render_human.py`: 全身モデルの撮影・ポーズプレビュー
- `poseforge/model_inspect.py`: 全身骨格調査
- `poseforge/create_human.py`: MPFBモデル生成

## 残る課題

モデルごとのIK、身体の自然なポーズ、物体保持の接触解決、メッシュの貫通判定、全身の動作プリセット。いずれも現時点で未完成です。Blender 5.2実機での新レンダリング経路の検証も未実施です。

## 指先の座標目標をAIから指定する（実験版）

`examples/human_finger_reach.json` は `pose.action=reach` の例です。指先の意味名（例 `right_index`）と `position: [x,y,z]` を指定し、Blenderのワールド座標（メートル）に向けてCCDで指関節を回転させます。

```powershell
py -m poseforge.cli render-reach examples/human_finger_reach.json --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

生成先 `output/human_finger_reach/report.json` に `targets[].error_m`、`converged`、`actual` を出力します。AIは誤差を読んでターゲットの再配置を判断できます。**現在は指関節のみを動かす位置IKです。** 肩・肘を含む全身IK、関節限界、衝突・接触検証、カード保持は未実装です。上の例の座標も到達を保証しません。