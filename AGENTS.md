# PoseForge AI開発ルール

- PoseForgeは**全身対応のAI向け3Dポーズ資料ツール**であり、手専用に最適化してはいけない。
- MPFBの全身リグモデルを使用する。古い簡易プロキシへ戻さない。
- Actor / Action / Props / Constraints / Renderを分離する。特定モデルの骨名は`rig.py`で吸収する。
- ポーズが視覚プレビューである場合、実際のIK・接触・貫通判定が済んだと主張しない。
- 出力とローカルのモデルは`output/`・`assets/`に置き、Gitで追跡しない。
- 本体はオフラインで実行。初回のMPFBセットアップのみオンライン可。
- `py -m unittest discover -s tests -v`を実行。Blender 5.2の実機レンダリングは別途行う。
- mainへ直接コミットする運用。ユーザーが望まないPRを作らない。
