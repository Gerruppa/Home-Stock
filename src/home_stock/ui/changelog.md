# Historia zmian

## Nieopublikowane

### Nowe funkcje
- Produkt może mieć zwykły termin ważności w dniach („zwykle ważne 7 dni”): zakup i pierwsza partia nowego produktu dostają wtedy od razu datę ważności, którą można zmienić.
- Zakup, także odhaczony na liście zakupów, można cofnąć przyciskiem „Cofnij”: dodana partia znika.
- Na karcie produktu „Zużyj” zdejmuje kilka sztuk naraz, zaczynając od partii z najbliższym terminem ważności; jedno „Cofnij” przywraca wszystkie partie.
- Lista zakupów podaje, ile sztuk kupić, a „Kopiuj listę” kopiuje ją jako zwykły tekst, a „Drukuj” otwiera czystą stronę do wydruku.
- „Rozpakuj zakupy” na liście zakupów zapisuje po powrocie ze sklepu wszystkie zaznaczone produkty naraz, z ilością i terminem ważności do poprawienia; jedno „Cofnij” usuwa wszystkie dodane partie.
- W „Rozpakuj zakupy” można dopisać po nazwie produkt spoza listy zakupów, kupiony przy okazji; zapisuje się i cofa razem z resztą.
- Kliknięcie pozycji na ekranie Start otwiera kartę produktu, skąd można wyrzucić przeterminowaną partię albo dodać zakup.
- Klawiatura: wyszukiwarka w Produktach od razu przyjmuje tekst i wraca pod Ctrl+F, a w oknach Enter zapisuje, Esc zamyka bez zapisu.
- Karta produktu pokazuje historię: ostatnie zużycia, zakupy, wyrzucenia (z oznaczeniem przeterminowanych) i ręczne korekty ilości, z datami. Historia zaczyna się od tej wersji, a „Cofnij” usuwa też jej wpis.
- Nowa zakładka Historia pokazuje 200 ostatnich zdarzeń wszystkich produktów, od najnowszych; wpisanie części nazwy zostawia tylko zdarzenia pasujących produktów.
- Produkty i karta produktu podają, na ile dni wystarczy zapas („wystarczy na ok. 12 dni”), liczone z zużyć z ostatnich 90 dni; prognoza pojawia się po co najmniej 3 zużyciach i 14 dniach historii.
- Na liście zakupów pojawia się też produkt, któremu zostało zapasu na tyle dni lub mniej, ile ustawisz w Ustawieniach jako „Zapas dni” (domyślnie 7), a każda pozycja mówi, dlaczego tam jest: „poniżej minimum” albo „wystarczy na ok. N dni”.
- Dla produktu z prognozą lista zakupów, „Kupione” i „Rozpakuj zakupy” proponują tyle sztuk, by ponad stan minimalny starczyło na „Zapas dni”, a karta produktu podpowiada stan minimalny dopasowany do zużycia („Sugerowany stan minimalny: 3”), który „Zastosuj” ustawia jednym kliknięciem, a „Cofnij” przywraca poprzedni.

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
