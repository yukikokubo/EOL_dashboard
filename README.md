# EOL Dashboard Sample

販売済みオフィス機器のEOLと保守期限を可視化するStreamlitサンプルアプリです。

## 起動方法

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## できること

- サンプルCSVまたはアップロードCSVを読み込み
- EOL/保守期限の期限切れ、90日以内、180日以内を集計
- 資産種別、メーカー、営業担当者、顧客別に可視化
- 期限が近い機器一覧を確認
- フィルター後のデータをCSVダウンロード

## CSV項目

`資産ID, 企業コード, 企業名, 営業担当者, 機器名, メーカー, 型番, 数量, 資産種別, EOL, 保守期限, 納品日, 設置場所, 登録日時, 更新日時`
