# 人体モデル導入（実験段階）

PoseForgeは全身モデルを基本単位とし、最初の検証ユースケースをカードのpinchとします。

## 候補

- **MakeHuman / MPFB**: 標準の人体アセットはCC0。アドオン本体にはGPL等の別ライセンスがあるため、コードを再配布する際は区別する。
- Blender Studio Human Base Meshes: CC0の素体候補。ただし**リグ付きとは限らない**ため、そのまま選択することはしない。

参考: https://www.makehumancommunity.org/about/license.html

モデルをBlenderで作成/書き出したら、.blend、.fbx、.glb、.gltfをローカルに保存してください。PoseForgeの実行時に通信する必要はありません。

## リグ構造の調査

```powershell
py -m poseforge.cli inspect-model "C:\path\to\character.fbx" --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

`character_rig_report.json` に、アーマチュアの有無、ボーン名、親子関係、各ボーンのローカル座標、指・四肢の候補が出力されます。出力先は `--output` で変更可能です。

**重要:** これはモデルの読み込み・調査機能です。既存の `render` コマンドは引き続き試作0の簡易形状を生成します。外部モデルでのポーズ適用、IK、接触判定はまだ未実装です。ボーン名の推測は完全ではありません。既存アセットの実際の仕様と手指の階層を確認してからアダプターを実装します。
