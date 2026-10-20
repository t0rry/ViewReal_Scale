# ViewReal

Blender の 3D ビューポートを、画面上で**実寸**に見えるようにズームするアドオンです。
ディスプレイのインチ数と解像度から画素密度（PPI）を計算し、ビューの中心にある物が実際の大きさで表示されるようにします。

## 対応環境
- Blender 4.2 以降（Blender 5.2 で動作確認済み）
- 解像度の自動取得は Windows のみ（他の OS は Manual で入力）

## インストール
1. Blender の `Edit > Preferences > Get Extensions` を開く
2. 右上の ▼ メニューから `Install from Disk...` を選ぶ
3. `dist/viewreal-1.1.0.zip` を選ぶ

## 使い方
1. 3D ビューポートで `N` キーを押してサイドバーを開き、`Item` タブの「ViewReal」パネルを見る
2. `Display Size (inch)` にディスプレイの対角インチ数を入れる
3. `Resolution` を選ぶ
   - **Auto**: 解像度を自動で取得する。`Detect` で取り直せる
   - **Manual**: X / Y を自分で入力する
4. `Scale` で表示倍率を決める（1.0 = 実寸、0.1 = 1/10、2.0 = 2倍）
5. 実寸で見たい物をビューの中心に置き（`テンキー .` でフォーカス）、`Set Real View` を押す

設定はアドオンの設定（Preferences）に保存されるので、どの .blend ファイルでも同じ値が使えます。

## 仕組み
- 目標: 1 Blender 単位 = `PPI ÷ 0.0254 × Unit Scale × Scale` px
- 今のズームで 1 単位が何 px か（投影行列とビューポートの幅から計算）を求め、その比で `view_distance` を変える
- 透視投影でも平行投影でも同じ計算で合う

## 注意
- 透視投影では、**ビューの中心と同じ奥行きにある物だけ**が実寸になります。手前の物は大きく、奥の物は小さく見えます
- ボタンを押したあとにビューポートの大きさを変えると、実寸からずれます。そのときはもう一度押してください
- ビューの操作は Blender の仕様で Ctrl+Z では戻りません
- カメラビューと 4分割表示（Quad View）には対応していません
- モニターが複数あるとき、Auto で取得するのはメインモニターの解像度です

## zip の作り直し
`viewreal/` を変更したら、このフォルダで次を実行します。

```
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --factory-startup --command extension build --source-dir viewreal --output-dir dist
```
