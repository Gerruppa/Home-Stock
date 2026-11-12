# Historia zmian

## Nieopublikowane

### Nowe funkcje
- W aplikacji na Androida działają już Start, Produkty (z kartą produktu, dodawaniem i edycją), Zakupy z rozpakowaniem zakupów, Historia (marnowanie z 30 i 90 dni, ostatnie zdarzenia i szukanie po nazwie produktu) oraz Ustawienia (zapas dni, kategorie z dniami ostrzeżenia, jednostki i przywracanie produktów z archiwum); listę zakupów można skopiować albo udostępnić, a dane zostają na telefonie.
- W aplikacji na Androida „Dodaj typowe produkty” w Ustawieniach i na pustej zakładce Produkty dodaje naraz zaznaczone typowe produkty, z jednym „Cofnij”; tak nowy telefon dostaje swoje produkty.
- W aplikacji na Androida wersja na dole Ustawień otwiera historię zmian, a pierwsze uruchomienie nowej wersji pokazuje „Co nowego”.
- W aplikacji na Androida, gdy na GitHubie jest nowsza wersja, obok numeru wersji w Ustawieniach pojawia się „Dostępna wersja X”; dotknięcie pobiera nową aplikację, którą instalujesz na starej, a dane zostają.
- W aplikacji na Androida na zakładce Zakupy założysz listę własną na okazję, np. „Kolacja w sobotę”, z datą albo bez, i dopiszesz do niej produkty z ilością albo cokolwiek innego, niezależnie od tego, czego brakuje.
- W aplikacji na Androida pozycje listy własnej odhaczasz w sklepie (produkt od razu trafia do zapasów, z ilością z listy), a kupione przechodzą pod „Kupione”; pozycje i całe listy można zmieniać i usuwać, każdą zmianę z „Cofnij”.

## 0.4.0 — 2026-11-02

### Nowe funkcje
- „Dodaj typowe produkty” w Ustawieniach (i na pustej zakładce Produkty) dodaje naraz zaznaczone spośród ok. stu produktów, które ma zwykle każdy dom, z kategorią, jednostką i zwykłym terminem ważności, bez stanu minimalnego; jedno „Cofnij” usuwa je wszystkie.

## 0.3.0 — 2026-11-02

### Nowe funkcje
- Produkt może mieć zwykły termin ważności w dniach („zwykle ważne 7 dni”): zakup i pierwsza partia nowego produktu dostają wtedy od razu datę ważności, którą można zmienić.
- Zakup, także odhaczony na liście zakupów, można cofnąć przyciskiem „Cofnij”: dodana partia znika.
- Na karcie produktu „Zużyj” zdejmuje kilka sztuk naraz, zaczynając od partii z najbliższym terminem ważności; jedno „Cofnij” przywraca wszystkie partie.
- Lista zakupów podaje, ile sztuk kupić, a „Kopiuj listę” kopiuje ją jako zwykły tekst, a „Drukuj” otwiera czystą stronę do wydruku.
- „Rozpakuj zakupy” na liście zakupów zapisuje po powrocie ze sklepu wszystkie zaznaczone produkty naraz, z ilością i terminem ważności do poprawienia; jedno „Cofnij” usuwa wszystkie dodane partie.
- W „Rozpakuj zakupy” można dopisać po nazwie produkt spoza listy zakupów, kupiony przy okazji; zapisuje się i cofa razem z resztą.
- Kliknięcie pozycji na ekranie Start otwiera kartę produktu, skąd można wyrzucić przeterminowaną partię albo dodać zakup.
- Na karcie produktu przy terminie ważności partii widać, czy jest „przeterminowana” (na czerwono), czy „kończy się termin” (na pomarańczowo).
- Klawiatura: wyszukiwarka w Produktach od razu przyjmuje tekst i wraca pod Ctrl+F, a w oknach Enter zapisuje, Esc zamyka bez zapisu.
- Karta produktu pokazuje historię: ostatnie zużycia, zakupy, wyrzucenia (z oznaczeniem przeterminowanych) i ręczne korekty ilości, z datami. Historia zaczyna się od tej wersji, a „Cofnij” usuwa też jej wpis.
- Nowa zakładka Historia pokazuje 200 ostatnich zdarzeń wszystkich produktów, od najnowszych; wpisanie części nazwy zostawia tylko zdarzenia pasujących produktów.
- Historia pokazuje też marnowanie: ile sztuk każdego produktu wyrzucono w ostatnich 30 i 90 dniach, od największej liczby, i ile z nich było przeterminowanych.
- Produkty i karta produktu podają, na ile dni wystarczy zapas („wystarczy na ok. 12 dni”), liczone z zużyć z ostatnich 90 dni; prognoza pojawia się po co najmniej 3 zużyciach i 14 dniach historii.
- Na liście zakupów pojawia się też produkt, któremu zostało zapasu na tyle dni lub mniej, ile ustawisz w Ustawieniach jako „Zapas dni” (domyślnie 7), a każda pozycja mówi, dlaczego tam jest: „poniżej minimum” albo „wystarczy na ok. N dni”.
- Dla produktu z prognozą lista zakupów, „Kupione” i „Rozpakuj zakupy” proponują tyle sztuk, by ponad stan minimalny starczyło na „Zapas dni”, a karta produktu podpowiada stan minimalny dopasowany do zużycia („Sugerowany stan minimalny: 3”), który „Zastosuj” ustawia jednym kliknięciem, a „Cofnij” przywraca poprzedni.
- Tryb demonstracyjny ma około dwóch miesięcy przykładowej historii, z zakupami takimi jak w domu (z terminem ważności) i zużyciami różnych produktów, więc od razu widać prognozy, produkt na liście zakupów z powodu kończącego się zapasu i marnowanie w Historii.

### Zmiany
- Na wąskim ekranie (telefon) pozycja listy zakupów ma dwa wiersze: nazwę z powodem, a pod nimi ilość, „kup” i „Kupione”, który nie wychodzi już poza kartę.
- Na wąskim ekranie karta produktu pokazuje cały termin ważności partii, a „Zapisz” i „Wyrzuć” są pod jej polami.
- Na wąskim ekranie Ustawienia pokazują pełne nazwy kategorii i jednostek, z dniami ostrzeżenia albo skrótem w wierszu pod nimi, a opis „Zapasu dni” pod polem.

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
