# 💰 Rates Dashboard

Живой дашборд курсов валют: ЦБ РФ, XE (рыночные), XFeepay.

**🔗 [Открыть дашборд](https://SCRIMN.github.io/rates-dashboard)**

## Источники

| Источник | Обновление | Статус |
|----------|-----------|--------|
| ЦБ РФ | GitHub Action каждые 30 мин (пн-пт, 7-22 МСК) | ✅ live |
| XE / Рынок | Frankfurter API → GitHub Action | ✅ live |
| XFeepay | Ручное обновление `rates.json` / скрипт | 🟡 ожидание |

## Как обновить XFeepay

Отредактировать `rates.json`, добавив блок `xfee`:
```json
{
  "xfee": {
    "USD": 85.50,
    "EUR": 92.30,
    "CNY": 11.70
  }
}
```

## Структура

```
├── index.html          # Дашборд
├── rates.json          # Курсы (обновляется Action'ом)
├── xfee-rates.json     # Заглушка XFeepay
└── .github/workflows/
    └── update-rates.yml  # Автообновление курсов ЦБ + XE
```
