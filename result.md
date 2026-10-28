# Evidence školení

**Popis řešení úkolu v rámci výběrového řízení**

Pavel Studeník

### 1. Zvolené řešení

V rámci zadání jsem vytvořil jednoduchou webovou aplikaci v **Django**, která umožňuje evidovat školení zaměstnanců, sledovat jejich platnost a doporučovat vhodné termíny pro absolvování chybějících školení.

Aplikaci jsem připravil v Dockeru, pro její běh využil uWSGI a pomocí GitLab CI nastavil automatické nasazování na vlastní VPS. Součástí řešení je také skript `csv_import.py`, který převádí dodaná CSV data do formátu JSON. Ta se následně importují do databáze pomocí příkazu `import_json`.

Jako hlavní rozhraní jsem zvolil **Django administraci**. Vzhledem k časovému rozsahu testovacího úkolu mi dávalo větší smysl využít již hotové a ověřené řešení než vytvářet samostatné uživatelské rozhraní. Mohl jsem se tak více věnovat datovému modelu, logice aplikace a samotné funkčnosti. Úvodní stránka je proto zatím pouze provizorní.

**Co aplikace umí:**

- Zobrazit aktivní zaměstnance a jejich absolvovaná školení.
- Rozlišit platná, neplatná a chybějící povinná školení.
- Vyfiltrovat zaměstnance, kterým chybí platné povinné školení.
- Zobrazit historii školení konkrétního zaměstnance.
- Doporučit vhodné termíny s volnou kapacitou, přednostně pro chybějící povinná školení.

**Odkazy na řešení:**

- Aplikace: http://muni-exam.brno.pavelstudenik.cz
- GitHub: https://github.com/Pajinek/muni-dev-exam
- Vlastní GitLab: https://gitlab.slavicin.unart.cz/pajinek/muni-dev-exam

### 2. Práce se vstupními daty

Při zpracování dodaných dat jsem narazil na několik nesrovnalostí, se kterými bylo potřeba se vypořádat.

Jednalo se například o rozdílné kódování CSV souborů (UTF-8 a Windows-1250), různé oddělovače, duplicitní záznamy, neexistující zaměstnance nebo nejednotné formáty dat a cen. Objevily se také rozdílné názvy stejných útvarů a různě zapsaná doba platnosti školení.

Pro účely úkolu jsem si proto stanovil několik pravidel:

- Platnost školení se vyhodnocuje vůči aktuálnímu datu serveru, přestože dodaná data pocházejí z 1. 10. 2026.
- Povinná školení se určují podle zařazení zaměstnance, jeho pracovní pozice nebo obecné povinnosti pro všechny.
- Kontrola povinných školení se týká pouze aktivních zaměstnanců.
- Prázdná nebo nulová doba platnosti znamená školení bez časového omezení.
- Doporučení termínů zohledňuje volnou kapacitu a vhodnost pro konkrétního zaměstnance, nikoliv celkovou optimalizaci všech přihlášek.

Tyto předpoklady jsem zvolil tak, aby bylo možné nad dodanými daty vytvořit funkční řešení bez nutnosti dalších upřesnění zadání.

### 3. Co jsem v rámci testu vynechal

Vzhledem k omezenému času jsem se soustředil především na funkčnost požadovanou zadáním. Některé věci jsem proto záměrně neřešil nebo je ponechal pouze v základní podobě.

Jde zejména o samostatné uživatelské rozhraní, pokročilé plánování kapacit, úplné sjednocení vstupních dat a podrobnější správu uživatelských oprávnění. Nedokončil jsem také překlady některých částí administrace do češtiny.

V aplikaci je použitá databáze SQLite, která je pro účely tohoto testu dostačující. Pro skutečný provoz bych zvolil PostgreSQL a více se zaměřil na zabezpečení osobních údajů, řízení přístupů a provozní monitoring.

### 4. Co bych řešil dál

Pokud by se mělo řešení dále rozvíjet, zaměřil bych se na přehlednější uživatelské rozhraní pro personalisty a vedoucí pracovníky, statistiky platnosti školení, automatická upozornění a možnost přímého přihlašování zaměstnanců na jednotlivé termíny.

### 5. Využití AI při vývoji

Při řešení úkolu jsem využíval **Cursor (Composer)** jako pomocníka při psaní kódu. Pomohl mi především s přípravou základní struktury Django projektu, administrace, importních skriptů, testů, automatizace nasazení a dokumentace.

Vygenerovaný kód jsem průběžně kontroloval, testoval a upravoval. Nejvíce vlastní pozornosti vyžadovala logika povinných školení, práce s nekonzistentními daty a návrh databázového modelu celého systému.

**Při práci s AI jsem postupoval po menších, jasně vymezených krocích.** Namísto zadávání rozsáhlých a složitých úkolů najednou jsem jednotlivé části řešení postupně navrhoval, implementoval a ověřoval. Tento přístup mi umožnil mít nad výsledným kódem lepší kontrolu, průběžně odhalovat chyby a vyhnout se zbytečně komplikovaným řešením.

### Závěrem

Cílem pro mě nebylo vytvořit během testovacího úkolu kompletní produkční aplikaci, ale ukázat způsob, jakým přistupuji k návrhu řešení, práci s daty a vývoji aplikací.

Snažil jsem se zvolit jednoduché a funkční řešení, které splňuje hlavní požadavky zadání a zároveň poskytuje rozumný základ pro případný další vývoj.
