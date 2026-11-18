# Rugby Analytics

Aplikacja analityczna dla **rugby union (15-osobowego)**. Projekt jest we wczesnej fazie prototypu.

## Funkcje w wersji 0.1.0

- Responsywny interfejs po polsku.
- Panel główny, baza reprezentacji i sekcja Rugby World Cup.
- Prognozator w przeglądarce: rating Elo, symulacja punktów i Monte Carlo.
- API w Pythonie/FastAPI z endpointami `/health`, `/teams` i `/predict`.
- Oddzielny moduł modelu z funkcją Elo i symulacją zdarzeń punktowych.

## Uruchomienie interfejsu

Otwórz `index.html` w przeglądarce lub uruchom lokalny serwer statyczny:

```bash
python -m http.server 8080
```

Następnie przejdź do `http://localhost:8080`.

## Uruchomienie API

Wymagany Python 3.10+.

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Dokumentacja API: `http://127.0.0.1:8000/docs`.

Przykładowe żądanie:

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"team_a":"NZL","team_b":"IRE","venue":"neutral","simulations":20000,"seed":42}'
```

## Import wyników historycznych

Projekt zawiera importer męskich meczów testowych (rugby union) z publicznego endpointu JSON serwisu TheBreakdown, którego rekordy wskazują na World Rugby match feed. Import obejmuje dostępne zakończone mecze i stronicuje odpowiedź API.

Po instalacji zależności uruchom w katalogu głównym repozytorium:

```bash
python scripts/import_historical_results.py
```

Przydatne parametry:

```bash
python scripts/import_historical_results.py --start-year 1990 --end-year 2026
python scripts/import_historical_results.py --output data/tests.csv --page-size 100
```

Wynik trafia domyślnie do `data/international_results.csv`. Importer zachowuje identyfikator meczu, datę, nazwy drużyn w postaci slugów, wynik, rozgrywki, miejsce i pole `confidence`. Rekordy bez poprawnej daty lub wyniku są pomijane. Pole `neutral` pozostaje puste, ponieważ nie należy zgadywać neutralnego boiska na podstawie samego wyniku.

**Ograniczenia źródła:** publiczna dostępność endpointu nie oznacza automatycznie licencji na dalszą dystrybucję danych. Przed publikacją pobranego CSV należy sprawdzić aktualne warunki serwisu. Stare mecze mogą mieć niepełne wyniki lub niższy poziom pewności. Import nie pobiera jeszcze statystyk szczegółowych, składów ani zdarzeń punktowych. Nie jest też jeszcze podłączony do modelu prognoz.

## Ważne: status danych i modelu

Dane drużyn w wersji 0.1.0 to **demonstracyjne wartości startowe (priors)**, a nie aktualny ani historyczny ranking World Rugby. Nie podłączono jeszcze zewnętrznego źródła wyników ani kursów. Prognozy nie są zweryfikowane i nie powinny być wykorzystywane jako rekomendacje zakładów.

Przed użyciem produkcyjnym należy:
1. pozyskać i udokumentować licencjonowane/wiarygodne dane historyczne,
2. znormalizować mecze, turnieje, wyniki i statystyki punktowania,
3. wyliczać ratingi i parametry z danych, zamiast wpisywać je ręcznie,
4. przeprowadzić chronologiczny backtest oraz sprawdzić Brier Score, log loss i kalibrację,
5. uwzględnić składy, kontuzje, czerwone kartki, pogodę, podróże i neutralne boisko,
6. zbudować symulator turniejów zgodny z regulaminem konkretnej edycji Rugby World Cup.

## Plan rozwoju

- **Etap 1:** prototyp interfejsu i bazowy silnik prognoz.
- **Etap 2:** import danych historycznych i aktualnych wyników.
- **Etap 3:** kalibracja modeli i backtesting.
- **Etap 4:** symulator Rugby World Cup.
- **Etap 5:** kursy, prawdopodobieństwa implikowane i analiza value.
- **Etap 6:** automatyczne aktualizacje i monitoring jakości danych.

## Struktura

```text
.
├── index.html
├── styles.css
├── app.js
├── backend/
│   ├── __init__.py
│   ├── main.py
│   └── model.py
├── scripts/\n│   └── import_historical_results.py\n├── data/\n│   └── .gitkeep\n├── requirements.txt
└── .gitignore
```
