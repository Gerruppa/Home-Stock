# Historia zmian

## Nieopublikowane

### Nowe funkcje
- Produkt może mieć zwykły termin ważności w dniach („zwykle ważne 7 dni”): zakup i pierwsza partia nowego produktu dostają wtedy od razu datę ważności, którą można zmienić.
- Zakup, także odhaczony na liście zakupów, można cofnąć przyciskiem „Cofnij”: dodana partia znika.
- Na karcie produktu „Zużyj” zdejmuje kilka sztuk naraz, zaczynając od partii z najbliższym terminem ważności; jedno „Cofnij” przywraca wszystkie partie.
- Kliknięcie pozycji na ekranie Start otwiera kartę produktu, skąd można wyrzucić przeterminowaną partię albo dodać zakup.

## 0.2.1 — 2026-11-01

### Zmiany
- Nowy wygląd: jasny motyw w zieleni, czytelne zakładki i karty z kolorem według pilności (przeterminowane na czerwono, kończący się termin na bursztynowo, do kupienia na niebiesko), a w Produktach ilość poniżej minimum jest wyróżniona.
- Na ekranie Start nazwa produktu stoi po lewej, a ilość i termin po prawej; okna (karta produktu, formularze, zakup, aktualizacja) i pasek „Cofnij” mają ten sam wygląd co zakładki.

## 0.2.0 — 2026-10-31

### Nowe funkcje
- Przy każdym uruchomieniu, zanim baza zostanie zaktualizowana, Home Stock zapisuje jej kopię zapasową w folderze danych i zachowuje 30 najnowszych.
- Nagłówek pokazuje wersję programu; kliknięcie jej otwiera tę historię zmian.
- Pierwsze uruchomienie nowej wersji pokazuje raz okno „Co nowego” z jej zmianami.
- Gdy na GitHubie jest nowsza wersja, obok numeru wersji pojawia się „Dostępna wersja X”; jedno kliknięcie pobiera instalator i aktualizuje program, a dane zostają.

## 0.1.0 — 2026-10-28

Pierwsza wersja: ręczny spis tego, co jest w domu, z przypomnieniami o kończących się zapasach i terminach ważności.

### Nowe funkcje
- Produkty z kategorią, jednostką, opcjonalnym rozmiarem opakowania i minimalnym zapasem, pogrupowane według kategorii, z wyszukiwarką.
- Partie z ilością i opcjonalną datą ważności: „−1” zużywa sztukę z partii o najbliższym terminie, a na karcie Produktu można poprawić lub wyrzucić partię.
- Zakładka Start pokazuje, co jest przeterminowane, czemu kończy się termin i co trzeba kupić.
- Lista zakupów wynika z minimalnych zapasów; zaznaczenie Produktu zapisuje zakup z proponowaną ilością.
- Produkty można archiwizować i przywracać, a po zużyciu, wyrzuceniu lub archiwizacji przez kilka sekund widać „Cofnij”.
- W Ustawieniach można dodawać i zmieniać kategorie (z liczbą dni ostrzeżenia przed terminem) i jednostki, a nieużywane usuwać.
- Tryb demonstracyjny (`--demo`) otwiera w przeglądarce przykładowe zapasy na osobnej, tymczasowej bazie.
