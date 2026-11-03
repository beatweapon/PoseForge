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

## 腕全体の到達IK（実験版）

`render-hand-reach` は左右の腕のボーンを用いて、手首の関節位置を目標座標へ近づけます。

```powershell
py -m poseforge.cli render-hand-reach examples/human_hand_reach.json --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

`output/human_hand_reach/report.json` の `targets[0].error_m` と `converged` で位置誤差を確認できます。手の向き・関節の可動域・接触や衝突は未解決で、見た目が自然である保証はありません。


## GitHub Actions 自動検証

`main` への push または Actions の手動実行で `.github/workflows/blender-smoke.yml` が起動します。Linuxランナーに **Blender 5.2.3 LTS** と **MPFB** を用意し、人体生成・Python単体テスト・ニュートラル/腕IK/指IK/カードプレビューを確認します。CIはヘッドレス安定性のため `BLENDER_WORKBENCH` で512pxの3視点を描画します（通常CLIのEEVEE設定は変更しません）。

各実行の Actions **Artifacts** に `poseforge-smoke-<run id>` が保存され、シーンごとのPNG、JSON、summary.md をダウンロードできます。Artifacts保持は14日です。Blenderの初期セットアップやネットワーク障害でもCIは失敗します。**スモークテストの成功は、正しいカード把持やIK収束を意味しません。** 今後の自動評価では接触距離・関節制限・貫通検出を別途追加します。


## Two-finger card grasp preview (experimental)

Run `py -m poseforge.cli render-grasp-card examples/human_card_grasp.json --blender BLENDER_PATH` to solve arm placement followed by thumb and index fingertip goals on opposite sides of the card. The `output/human_card_grasp/report.json` file includes `arm_reach` and `targets` with final world-space bone-tip errors. This is a **positional skeleton preview only**: it does not validate skin contact, anatomical joint limits, collision freedom, or whether the card can actually be held.


## 検証の基準と前提の見直し（2026-11）

指先の骨先端がカード目標点から3mm以内でも、見た目が自然にカードを保持しているとは限りません。実際にその問題が確認されたため、`grasp_card` のCIでは **骨先端の位置誤差（5mm超を回帰失敗とする）** に加え、MPFBの変形済みメッシュから指のウェイトに属する頂点を抽出し、カードの表面目標への距離とカード内に入ったサンプル頂点数を `skin_contact_diagnostics` に出力します。

この頂点サンプリングは簡易診断であり、**接触面の完全な衝突判定ではありません**。指の自然な曲がり、指腹接触、手の向き、関節限界を今後の設計課題とします。数字だけを最適化せず、CIの複数視点画像を確認して進めます。


## Semantic card presentation (experimental)

`render-present-card` accepts actor-relative placement, rather than guessing absolute world-space XYZ coordinates. See `examples/human_card_present.json`.

```powershell
py -m poseforge.cli render-present-card examples/human_card_present.json --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

Specify `pose.action="present_card"`, `hand="right"`, `presentation="chest_display"`, and the card `size` in meters. The card is placed using the rig's measured shoulder location and a fixed chest-forward offset. The old `grasp_card` action remains available as a comparison control.

`report.json` now contains `presentation` and `arm_posture` (elbow height and rough elbow angle) alongside finger-tip and skin-sampling metrics. This is an **experimental placement preset**, not an anatomical posture solver: there is no joint-angle constraint or full mesh collision validation. A CI pass means the pipeline executed, not that the character holds the card convincingly.


## Pinch pose-prior experiment (2026-11-03)

The semantic `present_card` action uses `poseforge/pose_prior.py` to apply a conservative local joint-angle hand template before arm IK. It then allows at most three limited CCD correction iterations (0.04 radian per joint step) on thumb/index. This avoids prioritizing a tiny bone-tip error over the hand's shape. The older `grasp_card` is deliberately unchanged as a numerical baseline.

`report.json > arm_reach.pose_prior` includes the template's joint angles, initial/final errors and whether the prior or bounded correction was selected. The pose-prior angles are only **experimental guesses** in MPFB local axes, not calibrated anatomy or verified joint limits; the rendered views must be inspected before treating them as a natural pinch.


## Generic prop grip frames (experimental)

`poseforge/grip_targets.py` accepts a set of world-space grip frames with `hand` (`left` / `right`), `grip_world`, `wrist_offset`, and `approach_axis_world`. It applies position IK to each wrist, then a **bounded** wrist rotation (at most 0.20 radians) toward the chosen hand axis, and remeasures both wrists. The result reports wrist-position error and the angle between the measured wrist-to-index-knuckle vector and the requested approach axis.

Two different objects now share this solver: `render-hold-bow` and `render-hold-staff` (see `examples/human_staff_hold.json`). Both produce six views from one unchanged 3D scene, with one rigid prop. These grip frames are internal Blender-facing data; direct arbitrary-prop JSON authoring is a future milestone. Neither contact, finger wrapping, collision avoidance, nor anatomically valid wrist orientation is verified by this first pass.


## Cylindrical handle finger prior (experimental)

Bow and staff now share a grip template in `poseforge/grip_pose.py`. After arm IK, the solver evaluates two opposite signs of MPFB local finger curl, chooses the lower **skeletal fingertip-to-handle-axis proxy cost**, then records per-finger distances, trials, and the chosen sign in `targets[].finger_grip_prior` of `report.json`. Handle axis/radius are defined by the same prop's grip frame. It is a geometry experiment; local angles and actual palm/finger skin contact have **not** been anatomically calibrated. It cannot prove a realistic wrap, joint compliance, nor absence of intersections. Images from front/back/side/hand_closeup remain essential.


## Palm-plane grip orientation (experimental)

The shared prop solver now estimates a hand plane from the wrist, index knuckle, and pinky knuckle. It reports `palm_frame_before` and `palm_frame_after` on each grip, and evaluates a small plus/minus 0.16-radian wrist roll without allowing a worse combined direction/plane score. The palm plane is deliberately **unoriented**: without calibrating the mesh's palm-facing side, its normal is ambiguous. This is not yet correct palm-to-handle surface contact, and skeletal proximity alone must never be treated as a verified hold. CI includes both bow and staff regressions.
