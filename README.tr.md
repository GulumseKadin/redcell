# redcell

<div align="center">

<video src="https://github.com/GulumseKadin/redcell/raw/main/promo/out/redcell-promo.mp4"
       poster="https://github.com/GulumseKadin/redcell/raw/main/promo/poster.png"
       controls muted loop width="860">
  <a href="https://github.com/GulumseKadin/redcell/raw/main/promo/out/redcell-promo.mp4">REDCELL tanıtım videosunu izle (26 saniye)</a>
</video>

</div>

redcell, Python ile yetkili ve otonom bir red-team ajanı kurmak için bir çatıdır. Doğru yapması zahmetli olan parçaları hazır verir: bir ReAct ajan döngüsü, değiştirilebilir LLM sağlayıcıları, MCP tarzı bir araç kayıt defteri, ortak bir bulgu deposu, CVSS 4.0 skorlaması ve bir hedefe dokunan her eylemin önünde duran bir scope (kapsam) ve onay kapısı.

Scope kapısının mantığı yalındır. Ajan yalnızca `scope.yaml` içinde listelediğin host ve alan adlarına karşı iş yapabilir ve varsayılan olarak her eylemden önce sana sorar. Geri kalan her şey, makinenden tek bir paket çıkmadan reddedilir.

İngilizce sürüm: [README.md](README.md).

## Önce güvenlik

redcell'i yalnızca sahibi olduğun ya da test etmek için yazılı iznin bulunan sistemlere karşı kullan. Her araç çağrısının hedefi izin listene göre denetlenir; listenin dışındaki her şey engellenir ve koşunun denetim kaydına yazılır. Geliştirme veya deneme yaparken `REDCELL_DRY_RUN=true` ayarını ver; ajan akıl yürütür ve araç seçer, ama hiçbirini çalıştırmaz.

## Kurulum

redcell için Python 3.11 veya üzeri gerekir.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Temel kurulum, API anahtarı olmadan yerel bir Ollama ile çalışır. İhtiyaç duydukça ek paketleri kur:

```bash
pip install -e ".[anthropic]"   # Claude sağlayıcısı
pip install -e ".[cvss]"        # gerçek CVSS 4.0 skorlaması
pip install -e ".[mcp]"         # dış araç sunucularına bağlanma
pip install -e ".[neo4j]"       # graf tabanlı durum deposu
```

`cvss` ek paketi olmadan bulgular yine kaydedilir, ama raporda skorları "not scored" (skorlanmadı) olarak görünür.

## Komutlar

```
redcell onboard                 başlangıç .env dosyası yazar
redcell scope init              başlangıç scope.yaml dosyası yazar
redcell tools                   kayıtlı araçları listeler
redcell run HEDEF               ajanları mevcut kapsama karşı çalıştırır
redcell report                  bulgu deposunu Markdown'a döker
redcell bench scenarios.yaml    kıyas (benchmark) senaryolarını çalıştırır
redcell version                 sürümü yazar
```

`run` komutunun birkaç seçeneği var:

```
--router rule|llm   rule deterministiktir (varsayılan); llm, sonraki aşamayı bir modele seçtirir
--ui                düz log satırları yerine canlı çok-ajanlı bir panel gösterir
--mcp "<komut>"     bir stdio MCP sunucusu başlatır ve araçlarını kaydeder
--yes, -y           kapsam içindeki eylemleri otomatik onaylar (etkileşimsiz). Kapsam yine de zorlanır
--no-banner         açılış animasyonunu atlar
```

## Yapılandırma

redcell ayarlarını ortam değişkenlerinden veya çalışma dizinindeki bir `.env` dosyasından okur.

```
REDCELL_PROVIDER        anthropic veya ollama
ANTHROPIC_API_KEY       sağlayıcı anthropic olduğunda anahtarın
OLLAMA_BASE_URL         varsayılan http://localhost:11434
REDCELL_SCOPE_FILE      scope dosyanın yolu (varsayılan scope.yaml)
REDCELL_REQUIRE_APPROVAL  true her eylemden önce sorar, false gözetimsiz çalışır
REDCELL_DRY_RUN         true akıl yürütür ve araç seçer ama hiçbirini çalıştırmaz
REDCELL_MAX_STEPS       ajan başına adım sınırı (varsayılan 25)
REDCELL_STORE           sqlite (varsayılan) veya neo4j
NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD   depo neo4j olduğunda kullanılır
REDCELL_REQUEST_TIMEOUT   LLM istek zaman aşımı, saniye (varsayılan 120)
REDCELL_MAX_RETRIES       Ollama geçici hatalarda yeniden deneme sayısı (varsayılan 2)
```

Modeller isme göre değil, katmana (tier) göre seçilir. `config.py`, üç katmanı (HIGH, MID, LOW) somut modellere eşler; böylece modeli bir kez değiştirirsin ve bir katman isteyen her ajan onu izler. Keşif ve raporlama işi genelde daha ucuz katmanları, daha zor akıl yürütme ise HIGH katmanını kullanır.

---

## Senaryo 1: API anahtarı olmadan yerel bir koşu

redcell'in uçtan uca çalışmasını görmenin en hızlı yolu budur. Yerel bir Ollama sunucusu kullanır; yani anahtar yok, bulut çağrısı yok. Hedef, Nmap projesinin tam da taranması için çalıştırdığı `scanme.nmap.org` sunucusudur.

### 1. Ollama'yı başlat ve bir model indir

```bash
ollama serve &
ollama pull qwen3:4b-instruct
```

`config.py`, MID ve LOW katmanlarını `qwen3:4b-instruct`, HIGH katmanını ise `qwen3:14b` modeline yönlendirir. Makinenin kaldırabildiğini indir ve katman eşlemesini ona göre ayarla.

### 2. Kapsamı yaz

```bash
redcell scope init
```

`scope.yaml` dosyasını yalnızca test hedefini yetkilendirecek biçimde düzenle:

```yaml
name: "scanme.nmap.org demo"
authorization_ref: "NMAP-PUBLIC-TEST-HOST"
allow:
  hosts: []
  domains: ["scanme.nmap.org"]
deny:
  hosts: []
```

### 3. Çalıştır

Sağlayıcı ve kapsam ortamdan gelebilir:

```bash
export REDCELL_PROVIDER=ollama
export REDCELL_REQUIRE_APPROVAL=false
export REDCELL_SCOPE_FILE=scope.yaml

redcell run "Fingerprint the public web service at scanme.nmap.org and record what you find." --router rule --yes
```

Koşu banner ile açılır, bağlı olduğu kapsamı yazar, sonra dört ajanı sırayla geçer. Gerçek çıktının kısaltılmış hali:

```
[●] REDCELL v0.0.1  ·  authorized red-team agent
Scope: scanme.nmap.org demo (NMAP-PUBLIC-TEST-HOST)
Provider: ollama
Store: sqlite

▶ stage: recon
→ http_fingerprint {'target': 'http://scanme.nmap.org'}
✓ recon done

▶ stage: exploit
→ record_finding {'title': 'Outdated Apache Server Version ...',
                  'cvss': 'CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/...'}
✓ exploit done

▶ stage: verify
✓ confirmed: Apache/2.4.7 (Ubuntu), known CVEs
✓ verify done

▶ stage: report
Scope audit: 4 allowed, 0 blocked
Run complete. Use `redcell report` to render findings.
```

`recon` ajanı siteyi parmak izledi ve gerçek sunucu başlığını, `Apache/2.4.7 (Ubuntu)`, geri okudu. `exploit` ve `verify` ajanları bu eski sürüm için bir bulgu kaydedip doğruladı ve onu bir CVSS 4.0 vektörüyle skorladı. Son satır denetim özetidir: kapsam içinde dört eylem çalıştı ve hiçbir şey engellenmedi.

### 4. Raporu oku

```bash
redcell report --out report_scanme.md
```

Markdown raporu her bulguyu kanıtı, CVSS 4.0 skoru ve önem derecesi, bir kanıt (proof-of-concept) bloğu ve bir düzeltme notuyla listeler. Bu koşuda öne çıkan bulgu, 9.3 (Critical) skorlu eski Apache sürümüdür.

## Senaryo 2: Claude ile denetimli ve elle onaylı bir koşu

İkinci senaryo, gerçek bir angajmanı nasıl yürütürdüğünü gösterir: akıl yürütmeyi yapan bir bulut modeli, bir sonraki adıma karar veren LLM router ve her eylemi elle onaylayan sen. Hiçbir şey gözetimsiz çalışmaz ve kapsamının kapsamadığı her şey reddedilir.

### 1. redcell'i Claude'a yönlendir

```bash
redcell onboard          # .env yazar
```

`.env` dosyasını düzenle:

```
REDCELL_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
REDCELL_REQUIRE_APPROVAL=true
REDCELL_SCOPE_FILE=scope.yaml
```

### 2. Angajmanın kapsamını belirle

`scope.yaml` içine yalnızca yetkilendirmende adı geçen sistemleri koy ve yetki referansını gerçek belgeye ya da kayda bağlı tut:

```yaml
name: "Acme staging assessment"
authorization_ref: "SOW-2026-114"
allow:
  hosts: ["10.20.0.0/24"]
  domains: ["staging.acme.example"]
deny:
  hosts: ["10.20.0.9"]   # aralıkta olan ama dokunmaman gereken tek makine
```

### 3. LLM router ile çalıştır ve her adımı onayla

Kapı her eylemden önce sorsun diye `--yes` verme:

```bash
redcell run "Enumerate the staging web tier and confirm anything you find" --router llm
```

Onay açık olduğu için hedefe dokunan her eylem senin kararın için durur. İstem, neyin nerede çalışacağını açıkça yazar:

```
▶ stage: recon
⇢ route (llm) → recon: no findings yet, start with discovery
[approval] run 'http_fingerprint' on 'http://staging.acme.example'? [y/N] y
→ http_fingerprint {'target': 'http://staging.acme.example'}
```

Model kapsamında olmayan bir hedef önerirse, kapı onu çalışmadan durdurur ve nedenini kaydeder:

```
[approval] run 'port_scan' on '10.20.0.9'? [y/N] y
✖ blocked: '10.20.0.9' is out of scope
```

Burada operatör evet dedi, ama deny listesi yine kazandı. Onay, kapsamı asla geçersiz kılmaz. Koşunun sonunda denetim satırı iki sonucu da toplar:

```
Scope audit: 6 allowed, 1 blocked {'allowed': 6, 'blocked:out-of-scope': 1}
```

### 4. Canlı izle ya da daha ağır araçları bağla

Bu senaryoyu iki yol genişletir.

Dört ajanın çalışmasını log satırları arasında kaydırmak yerine canlı bir panelde izlemek için `--ui` ekle. Panel stdin'i kendisi için kullandığından, kapsam içindeki eylemleri `--yes` gibi otomatik onaylar:

```bash
redcell run "Enumerate the staging web tier" --router llm --ui
```

Ajanlara yerleşik araç sarmalayıcılarının ötesinde gerçek araçlar vermek için bir dış MCP araç sunucusu başlat ve onu koşuya kaydet. O uzak araçlar yine aynı scope kapısından geçer:

```bash
redcell run "Enumerate the staging web tier" --mcp "python -m my_tool_server"
```

### 5. Raporu teslim et

```bash
redcell report --out acme_staging.md
```

Senaryo 1'deki ile aynı skorlanmış Markdown'ı alırsın; koşu sırasında ajanların gerçekten kaydedip doğruladığı şeylerden kurulur.

---

## Güvenlik kapısı nasıl çalışır

Her araç, bir hedefe dokunup dokunmadığını bildirir. Dokunuyorsa, araç çalışmadan önce `ScopeGuard` sırayla üç denetim yapar:

1. Hedef `scope.yaml` içinde mi ve deny listesinde değil mi? Değilse eylem kapsam dışı olarak engellenir.
2. Bu bir dry-run mı? `REDCELL_DRY_RUN=true` ise eylem engellenir ve yalnızca anlatılır.
3. Onay gerekiyor mu? Onay açıksa yapılandırılmış politika karar verir. Varsayılan politika stdin'den sorar; `--yes` ve benchmark aracı bunun yerine etkileşimsiz politikalar sağlar.

İzin verilen ya da engellenen her karar, koşunun denetim kaydına eklenir ve sonda özetlenir. Yalnızca yerel kayıt tutan araçlar, örneğin `record_finding`, bir hedef bildirmez ve hiçbir zaman kapıdan geçmez.

## Proje düzeni

```
src/redcell/
  cli.py              Typer CLI: onboard, scope, tools, run, report, bench
  config.py           ayarlar ve katman (HIGH/MID/LOW) ile model eşlemesi
  llm/                sağlayıcıdan bağımsız LLM geçidi
    providers/        anthropic.py, ollama.py
  tools/              MCP tarzı araç katmanı
    builtins.py       port_scan (nmap), http_fingerprint, record_finding
    mcp.py            stdio MCP istemcisi ve adaptörü
  agents/             ReAct döngüsü, uzman ajanlar ve orkestratör
    router.py         RuleRouter (varsayılan) ve LLMRouter
  safety/
    scope.py          kapsam izin listesi ve kapı
    approval.py       takılabilir onay politikaları (Cli, Auto, Callback)
  state/              bulgu deposu: varsayılan SQLite, isteğe bağlı Neo4j
  report/             Markdown raporu ve CVSS 4.0 skorlaması
  ui/                 banner ve canlı panel
tests/                kapsam kapısı testleriyle başlar
```

## Yapım durumu

Planlanan tüm fazlar yerinde. Test paketi önce scope kapısını, sonra geri kalanını kapsar.

- Faz 0: tek ajan, tek araç, tek model.
- Faz 1: sağlayıcı soyutlaması ve katman eşlemesi.
- Faz 2: MCP tarzı araç katmanı; gerçek stdio MCP istemcisi sonradan bağlandı.
- Faz 3: çok-ajanlı orkestrasyon (exploit, verify, report), durum güdümlü router (`--router rule|llm`), canlı panel (`--ui`) ve MCP araç istemcisi (`--mcp`).
- Faz 4: Store arayüzünün arkasında graf olarak ortak durum (`REDCELL_STORE=neo4j`), varsayılan SQLite.
- Faz 5: CVSS 4.0 skorlaması, kanıt yakalama ve bir benchmark aracı (`redcell bench`).
- Faz 6: gerçek LLM router. Amaca duyarlıdır, bulguların bütçelenmiş bir özetini tutar, tek satırlık gerekçeyi bir `route` olayı olarak gösterir, her aşamanın kaç kez tekrarlayacağını sınırlar ve her kötü yanıtta deterministik router'a döner.
- Faz 7: kanıt seviyesinde bulgular. `record_finding` aracı, exploit ve verify ajanlarının skorlanmış bir kayıt (başlık, CVSS 4.0 vektörü, kanıt, düzeltme) doğrudan rapora yazmasını sağlar.
- Faz 8: operatör onay deneyimi. Takılabilir bir `ApprovalPolicy` ham istemi değiştirir, `--yes` gözetimsiz çalışır ve her kapı kararı tutulup özetlenir.
- Faz 9: sağlayıcı sağlamlaştırma. Ollama sağlayıcısı geçici hataları geri çekilmeyle yeniden dener, bozuk bir araç-çağrısı argümanında çökmez ve tutarlı çok adımlı koşular için asistanın araç çağrılarını geçmişe geri besler.

## Testler

```bash
pytest
```

Paket çevrimdışı çalışır. Sağlayıcı çağrıları taklit edilir, Neo4j arka ucu Cypher'ı kaydeden sahte bir sürücüye karşı denenir ve `time.sleep` yamalanır; böylece yeniden deneme ve animasyon testleri hızlı kalır.
