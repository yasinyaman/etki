# Etki — Eklenti Arayüz İhtiyaçları Planı

| | |
|---|---|
| **Versiyon** | 0.1 |
| **Tarih** | 2026-07-15 |
| **İlgili doküman** | `Etki_Plugin_Gelistirme_Plani.md` (Faz 1–5 kırılımı) + `Etki_Plugin_Marketplace_Plani.md` (kilitli ilkeler) |
| **Kapsam** | Eklenti sisteminin web arayüzüne dokunduğu her nokta: yönetim ekranı tamamlama, adaptör seçiminin dinamikleşmesi, sağlık/degradasyon görünürlüğü, karar provenance'ı, `options_model`'den form üretimi |
| **Toplam süre** | ~3–4 hafta part-time |

> Bu plan "eklenti kendi arayüzünü getirmez" ilkesinin devamıdır: eklenti yalnızca **veri/deklarasyon** teslim eder (PluginSpec, manifest, options_model, lockfile kaydı), arayüz her zaman Etki'nin kendi ekranlarının bu verinin **projeksiyonu** olmasıyla oluşur. Plugin'lerin şablon/ekran/widget katkı mekanizması YOKTUR ve bu planda da açılmaz. Tüm dosya/satır referansları 2026-07-15 keşfine karşı doğrulanmıştır (çalışma ağacı, Faz 1–5 sonrası).

---

## A. Kesişen Tasarım Kararları

### A1. Kilitli kurallar (marketplace planından — yeniden tartışılmaz)

- **UI'dan asla kurulum yok.** Bu plandaki hiçbir iş kalemi kod-edinme endpoint'i ekleyemez; mevcut tek mutasyon (aktif/pasif toggle) genişletilirken de bu sınır korunur.
- **`ETKI_PLUGIN_POLICY` salt-okunur gösterilir** — env-only; UI hiçbir zaman yazamaz (`tests/unit/test_plugin_policy.py` ters-öncelik kanıtı bozulmadan kalır).
- **Secrets:** UI yalnızca `env:VAR` **referansını** gösterir/saklar; çözülmüş değer hiçbir template'e, log'a veya form value'suna girmez. Çözüm yalnız adapter-build anında core'da (`_resolve_secret_refs`).
- Tüm yeni string'ler **i18n tr/en/de** (`etki/i18n/catalog.py`, `t` Jinja global); tüm mutasyonlar **pmo-only + proje erişim guard'ı**; karar butonu kalıbına uygun **`hx-confirm`**.

### A2. Adaptör adlarının tek doğruluk kaynağı

Bugün work-items dropdown'ı template'te hardcoded `['none','file','jira','glpi']` ([project_files.html:83](etki/api/templates/project_files.html)); builtin ad listeleri ise yalnız `registry.py`'deki üç `_unknown(...)` çağrısının inline literal'lerinde yaşıyor. Karar:

- `etki/adapters/registry.py`'ye **`available_adapters(port) -> list[str]`** eklenir: builtin adlar (modül-seviyesi sabit listeden — literal'ler TEKİLLEŞİR, `_unknown` mesajları da buradan beslenir) + `get_plugin_registry().names(port)`. Builtin önceliği değişmez (builtin kazanır; plugin aynı adı gölgeleyemez).
- Doğrulama simetriktir: UI POST'u da aynı listeye karşı doğrular (bilinmeyen ad → 400 + mevcut liste). **YAML kaçış yolu açık kalır** — henüz kurulmamış bir plugin'in adı config dosyasına elle yazılabilir; UI formu güvenli/dar yüzeydir, config esnek yüzeydir (İlke: config > kod).
- `disabled`/`failed` durumdaki plugin'in adaptör adları listeye girmez (spec yüklenmemiş olabilir); dropdown yalnız o an çözülebilir adları gösterir.

### A3. Sağlık modeli: "yapılandırılmış fake" ≠ "degrade olmuş"

Faz 2 izolasyonu bozuk adaptörü sessizce `Fake…([])`'e düşürür ve **hiçbir UI bunu bilemez** ([context.py](etki/api/context.py) ~294–302/328–334 log-only; `AppContext`'te sağlık alanı yok). Proje ekranı "linear" yazmaya devam eder, havuzlar sessizce "—" olur. Karar:

- **`AdapterHealth` runtime kaydı** (persist edilmez — context her kurulduğunda tazedir): `AppContext.adapter_health: dict[project_id, list[AdapterHealth]]`, alanlar `port, adapter, state("ok"|"degraded"), error: str | None`. `get_context` build sırasında ve `refresh_pools()` hatalarında doldurur.
- Ayrım net: `adapter: fake`/`none` yapılandırılmış proje **ok**'tur (rozet yok); yapılandırılan adaptörün build'i/çağrısı patladığı için Fake'e düşen proje **degraded**'dır (rozet var).
- Rozet kalıbı mevcut index-staleness rozetinin kardeşidir ([project_detail.html:32](etki/api/templates/project_detail.html)); triyaj kararının içine sinyal SIZDIRMAZ (karar/güven/efor bayt-aynı — bu yalnız görünürlük katmanı).

### A4. Motor serbest-metni ve freeze disiplini (U3 için)

`_safe_find_similar` hatası bugün "benzer iş yok" ile ayırt edilemez ([triage.py](etki/engine/triage.py) ~894–903 → `[]`; kanıt zinciri `engine.cov.no_similar`/`engine.asm.no_history` üretir). Karar: hata yolunda **ayrı anahtar** (`engine.cov.history_unreachable` / `engine.asm.history_unreachable` — "Efor kaynağına ulaşılamadı → benzer-iş olmadan devam; karar etkilenmez"). Kurallar:

- **Karar/güven/efor bayt-aynı kalır** (boş liste zaten aynı estimation yoluna girer; yalnız dondurulan metin hata durumunda farklılaşır). Normal yol (gerçek sıfır-eşleşme) mevcut metni aynen üretir.
- Motor metni **karar anında proje dilinde** üretilip donar (mevcut invariant).
- **Freeze guard:** `engine/triage.py` değişikliği içeren PR `eval/datasets/**/*.json`'a DOKUNMAZ. Guard'ın izlediği prefix'ler yalnız `etki/engine/`, `etki/extraction/`, `etki/core/text.py` (doğrulandı) — `etki/i18n/catalog.py` izlenmez, yani U3.2'nin triage+catalog birlikte değişmesi serbesttir. Golden gate karar-seviyesi anlaşmadır; metin değişikliği 61/66'yı etkilemez — yine de CI'da doğrulanır.

### A5. `options_model`'den form üretimi (U4 için)

Marketplace planındaki "ileride UI form render edebilir" notu bu planda faza bağlanır. Karar:

- Kaynak: `AdapterFactory.options_model.model_json_schema()` (plugin) + builtin adaptörler için **yeni hafif opsiyon modelleri** (`etki/adapters/options.py`: `BUILTIN_OPTION_MODELS[port][name]` — alanlar `docs/adapters.md` tablolarından; builtin build'leri de bu modellerle doğrulanmaya geçer → çıplak `KeyError` yerine Pydantic mesajı; adaptör semantiği değişmez).
- Render kuralı dar tutulur: `string→text`, `number/integer→number`, `boolean→checkbox`; required işareti; default prefill; tanınmayan şema özelliği → o alan için text fallback. Serbest "key: value" textarea'sı **gelişmiş mod** olarak kalır (bilinmeyen/ekstra anahtarlar için kaçış yolu).
- Kaydette doğrulama `options_model.model_validate` ile yapılır ama **`env:` referansları ÇÖZÜLMEDEN** (str alanlarda `env:X` geçerli değerdir; env var'ın varlığı deploy'un işidir, formun değil). Form değerleri string gelir — Pydantic v2 lax modu `"4"→4.0`, `"true"→True` coercion'ını zaten yapar; checkbox işaretsizken alan hiç gönderilmez → model default'u geçerlidir. Doğrulama hatası → 400 + alan-seviyesi Pydantic mesajı, form değerleri korunur.

---

## B. Faz Bazında İş Kırılımı

### Faz U1 — Yönetim ekranı tamamlama + dinamik adaptör seçimi · **~0,5 hafta** · ✅ UYGULANDI 2026-07-15

**Hedef:** Kurulu bir eklenti, kurulumdan sonra hiçbir şablon düzenlemesi gerekmeden work-items formunda seçilebilir; Eklentiler ekranı elindeki veriyi tam gösterir.

> Uygulama notları: `registry.available_adapters(port)` + `_BUILTIN_ADAPTERS` sabiti (üç
> `_unknown` mesajı da buradan besleniyor); dropdown `work_item_adapters` context değişkeni
> ("fake" UI'dan gizli; yapılandırılmış-ama-çözülemeyen ad seçili kalır); POST doğrulaması
> `pf.unknown_adapter` (400 + mevcut liste, YAML kaçış yolu mesajda); Eklentiler ekranı
> Kaynak (lockfile `source`) + Uyum (`api_compat`) kolonları ve devre-dışı onayı
> (`plugins.confirm_disable`). Gate `tests/integration/test_plugins_ui.py` (dropdown'da
> `linear`, bilinmeyen ad 400, kolonlar+onay) + `tests/unit/test_plugin_registry.py`
> (`available_adapters` bileşimi). Doküman: writing-an-adapter.md "Your plugin in the UI".

| # | İş kalemi | Dosyalar (Y=yeni, D=değişir) | Testler |
|---|---|---|---|
| U1.1 | `available_adapters(port)` (A2): builtin sabit listesi tekilleşir, `_unknown` mesajları buradan beslenir | D `etki/adapters/registry.py` | unit: builtin+plugin bileşimi; plugin'siz kurulumda yalnız builtin'ler |
| U1.2 | Work-items dropdown dinamikleşir: `_files_context` (web.py ~1764) `available_adapters("work_items")` geçirir; eksik builtin'ler (gitlab/redmine/azure_devops) de listeye girer; POST (~1928) bilinmeyen adı 400 + mevcut liste ile reddeder; `projects_store.set_work_items` stale "(file \| jira \| glpi)" docstring'i düzeltilir | D `etki/api/web.py`, D `etki/api/templates/project_files.html`, D `etki/projects_store.py` | entegrasyon (TestClient, dev-group linear kuruluyken): dropdown `linear` içerir; bilinmeyen ad → 400; `linear` seçimi kaydolur + `_reindex` tetiklenir |
| U1.3 | Eklentiler ekranına `api_compat` kolonu + kurulum kaynağı (lockfile `source: git\|local\|verified` — `PluginStatus.source` sabit "plugin" olduğundan lockfile'dan türetilir); toggle'a `hx-confirm` (devre dışı bırakma projenin adaptörünü Fake'e düşürebilir — metin bunu söyler) | D `etki/api/templates/plugins.html`, D `etki/api/web.py`, D `etki/i18n/catalog.py` | entegrasyon: kolonlar render olur; toggle round-trip mevcut testte yeşil kalır |
| U1.4 | Doküman eş-güncelleme: `writing-an-adapter.md` stale "Faz 2 gelince" notu düşer; yeni bölüm "Eklentiniz arayüzde": Eklentiler ekranı, dropdown'da görünme, `options_model`→form (U4'e ileri referans), policy/CLI özeti | D `docs/writing-an-adapter.md` | — |

**Gate:** dev-group'taki `etki-plugin-linear` kuruluyken TestClient ile: (a) work-items formu `linear`'ı listeler ve kaydeder, (b) bilinmeyen ad 400 alır, (c) Eklentiler ekranı api_compat + kaynak gösterir. Policy-değiştiren POST yokluğu testi yeşil kalır.

**Riskler:** dropdown'a giren plugin adının plugin kaldırılınca kırık config bırakması (mevcut davranış: build hatası → Fake fallback; U2 rozeti tam bunu görünür kılar — sıralama gerekçesi).

---

### Faz U2 — Sağlık/degradasyon görünürlüğü · **~1 hafta** · ✅ UYGULANDI 2026-07-15

**Hedef:** PMO, bir projenin efor/doküman kaynağının koptuğunu log'a bakmadan görür; "sessiz ama yüksek sesli değil" boşluğu kapanır.

> Uygulama notları: `AdapterHealth` + `AppContext.adapter_health` / `degraded_adapters()`
> (`context.py`; work-items + documents fallback'leri kaydeder, `refresh_pools` hatası
> degrade eder ve BİLİNÇLİ olarak auto-heal etmez — Fake fallback üzerindeki başarılı
> refresh gerçek sorunu gizlemesin, iyileşme context rebuild'inde). Rozetler: Özet meta
> satırı (`pd.degraded_work_items/documents`, tooltip=hata) + Dosyalar work-items kartı
> + havuz kartında `rep.pool_degraded_note`. Ek sağlamlaştırma: `_files_context`'teki
> doküman listesi try/except'e alındı (bozuk doküman konektörü tam da onu düzelteceğin
> ekranı düşürüyordu). Gate: `tests/integration/test_adapter_health.py` (sağlıklı=rozetsiz,
> degraded=3 yüzeyde görünür, refresh-hatası degrade eder) + `test_plugin_runtime.py`
> genişletildi (fallback'in KAYITLI olduğu assert'lenir).

| # | İş kalemi | Dosyalar | Testler |
|---|---|---|---|
| U2.1 | `AdapterHealth` + `AppContext.adapter_health` (A3); `get_context` work-items/documents fallback'lerinde ve `refresh_pools` hata yolunda doldurulur | D `etki/api/context.py` | `tests/integration/test_plugin_runtime.py` genişler: bozuk factory → `adapter_health` `degraded` + hata metni; `adapter: fake` yapılandırması → `ok` |
| U2.2 | Proje ekranlarında rozet: Özet'te (staleness rozetinin yanı, "⚠ efor kaynağına ulaşılamıyor (linear) — efor geçmişi devre dışı") + Dosyalar work-items kartında aynı uyarı; yapılandırılan ad yanında gerçek durumu söyler (bugün ekran Fake'e düşmüşken "linear" yazar) | D `etki/api/templates/project_detail.html`, D `etki/api/templates/project_files.html`, D `etki/api/web.py`, D `etki/i18n/catalog.py` | entegrasyon: degraded projede rozet var; sağlıklı ve fake-yapılandırmalı projede yok |
| U2.3 | KPI/havuz boş-durumuna neden ipucu: havuz "—" iken proje degraded ise "efor kaynağına ulaşılamıyor" alt notu — Raporlar 2026-07'de Özet'e katıldığı için hedef `project_detail.html`'deki KPI/havuz kartlarıdır (`/projeler/{id}/raporlar` yalnız redirect) | D `etki/api/templates/project_detail.html`, D `etki/api/web.py` | entegrasyon: degraded projede not render olur |

**Gate:** kasıtlı-bozuk adaptörlü proje TestClient'ta: Özet rozet gösterir, Raporlar neden notu gösterir, `adapter: fake` projesi hiçbirini göstermez; `test_plugin_runtime.py` keep-serving assert'leri aynen yeşil.

**Riskler:** sağlık durumunun bayatlaması (`get_context` lru_cache'li — rozet "son context kuruluşu" anını yansıtır; rozete zaman damgası eklemek yerine bu semantik dokümante edilir); rozetin `viewer` rolüne de görünmesi bilinçlidir (salt-okunur bilgi).

---

### Faz U3 — Karar provenance + triyaj-anı ayrımı · **~0,5 hafta** · ✅ UYGULANDI 2026-07-15

**Hedef:** Hangi eklenti koduyla karar verildiği vaka ekranında görünür; "kaynak yok" ile "kaynağa ulaşılamadı" kanıt zincirinde ayrışır.

> Uygulama notları: `plugin_set` macros.html audit satırında yalnız dolu ise render
> (`ev.plugin_set`; `[]` vakalar bayt-aynı görünür — `test_plugin_provenance.py`).
> `_safe_find_similar` artık `(similars, unreachable)` döner; hata yolu
> `engine.cov.history_unreachable` / `engine.asm.history_unreachable` üretir, normal
> sıfır-eşleşme yolu bayt-aynı metin (`test_history_unreachable.py`: karar/güven/efor/risk
> iki yol arasında birebir eşit pinli). Freeze disiplini tutuldu: `eval/datasets`
> DOKUNULMADI, golden 61/66 değişmedi (eval runner GEÇTİ).

| # | İş kalemi | Dosyalar | Testler |
|---|---|---|---|
| U3.1 | `plugin_set` render: macros.html audit satırına (~138, model_version'ın yanı) yalnız **dolu ise** "Eklentiler: etki-plugin-linear@0.1.0" satırı; eski/plugin'siz vakalar (`[]`) değişmeden render olur | D `etki/api/templates/macros.html`, D `etki/i18n/catalog.py` | entegrasyon: plugin'li triyajda satır var; `[]` vakada yok (eski vaka fixture'ı) |
| U3.2 | `_safe_find_similar` ayrımı (A4): hata yolu `history_unreachable` coverage/assumption anahtarları üretir; karar/güven/efor bayt-aynı pinlenir | D `etki/engine/triage.py`, D `etki/i18n/catalog.py` (**bu PR'da `eval/datasets` düzenlemesi YOK**) | unit: raise eden provider → assumption "ulaşılamadı" varyantı, decision/confidence/effort normal sıfır-eşleşme yoluyla birebir aynı; golden 61/66 değişmez (CI) |

**Gate:** CI'da golden + backtest değişmeden geçer; kasıtlı-raise eden work-items provider'lı triyajın kanıt zinciri "ulaşılamadı" metnini taşır, kararı normal yolla özdeştir.

**Riskler:** freeze guard kombinasyon kuralı (U3.2 PR'ı dataset'e dokunamaz — A4); mevcut bayt-aynılık pinleyen testler (disputed/precedent testleri) yalnız normal yolu pinler, hata yolu yeni test alanıdır — çakışma beklenmez, koşularak doğrulanır.

---

### Faz U4 — `options_model`'den yapılandırılmış form · **~1–1,5 hafta** · ✅ UYGULANDI 2026-07-15

**Hedef:** Adaptör seçilince opsiyonlar serbest textarea yerine şemadan üretilmiş alanlarla girilir; yazım hataları kaydetme anında alan-seviyesi mesajla yakalanır.

> Uygulama notları: `etki/adapters/options.py` (6 builtin work-items modeli, `extra="allow"`
> — serbest mod/YAML'daki fazla anahtarlar geçer); builtin build'ler modellerle doğrular
> (KeyError → alan-seviyesi Pydantic mesajı); `registry.options_model_for(port, adapter)`
> builtin tablosu → plugin `options_model` sırasıyla çözer. Fragment
> `GET …/ayarlar/work-items/form?adapter=X[&mode=raw]` → `work_items_form.html`
> (şema→alan: string→text, number→number, boolean→checkbox, anyOf→text; `env:` referansı
> olduğu gibi; model yoksa/raw modda textarea); dropdown `hx-get`+`hx-include` ile formu
> tazeler. POST: typed alanlar `opt_*` (boş opsiyoneller düşer → model default'u),
> `options` textarea'sı varsa eski serbest yol; model varsa `model_validate` — `env:`
> ÇÖZÜLMEDEN (pf.invalid_options, 400'de girilen değerler korunur). Gate:
> `tests/unit/test_builtin_options.py` + `tests/integration/test_workitems_form.py`
> (linear+jira şemadan render, textarea fallback, hatalı tip 400+alan adı, geçerli kayıt
> 303+boş opsiyonel düşmüş). Golden 61/66 değişmedi.

| # | İş kalemi | Dosyalar | Testler |
|---|---|---|---|
| U4.1 | Builtin opsiyon modelleri (A5): `etki/adapters/options.py` — work_items builtin'lerinin alanları (`docs/adapters.md` ile eş); builtin build yolları bu modellerle doğrular (KeyError → Pydantic mesajı) | Y `etki/adapters/options.py`, D `etki/adapters/registry.py`, D `docs/adapters.md` | unit: her builtin model örnek options'la build'i geçer; eksik zorunlu alan → alan adı içeren ValueError |
| U4.2 | Şema→form fragment'i: `GET /projeler/{id}/ayarlar/work-items/form?adapter=X` (pmo-only) HTMX fragment'i döner — `options_model.model_json_schema()`'dan alanlar (A5 render kuralı), mevcut options prefill, `env:` referansları olduğu gibi text alanında; dropdown `hx-get` ile adaptör değişince formu tazeler; "gelişmiş mod" linki textarea'ya düşer | D `etki/api/web.py`, Y `etki/api/templates/work_items_form.html` (fragment), D `etki/api/templates/project_files.html`, D `etki/i18n/catalog.py` | entegrasyon: `linear` seçimi api_key/hours_per_point/timeout alanlarını üretir; jira builtin formu base_url/email/api_token üretir |
| U4.3 | Kaydet yolu doğrulamalı: POST work-items, seçilen adaptörün modeli varsa `model_validate` (env: çözmeden) → hata halinde 400 + alan mesajları + değerler korunur; model yoksa (gelişmiş mod / bilinmeyen ekstra anahtar) mevcut serbest yol | D `etki/api/web.py` | entegrasyon: `hours_per_point: abc` → 400 + alan mesajı; geçerli form → projects.yaml doğru şekil; `env:LINEAR_API_KEY` str alanında geçer |

**Gate:** linear (plugin) ve jira (builtin) için form şemadan render olur, hatalı tip alan-seviyesi mesajla reddedilir, geçerli kayıt `projects.yaml`'a bugünkü şekliyle yazılır ve `_reindex` sonrası triyaj çalışır; gelişmiş mod kaçış yolu yeşil.

**Riskler:** şema çevirisinin genişlemesi (önlem: A5 dar kural + text fallback — nested model/enum v1'de textarea'ya düşer); builtin modellerinin `docs/adapters.md` ile sapması (önlem: U4.1 testi dokümandaki alan adlarını assert eder); secret'ların yanlışlıkla düz metin girilmesi bugünkü davranışla aynı kalır (konvansiyon notu formda görünür — çözüm değil, hatırlatma).

---

## C. Sıralama ve Süre

```
U1 (0,5h) ──> U2 (1h) ──> U3 (0,5h) ──> U4 (1–1,5h)
```

U1→U2 sıralaması bilinçli: dropdown plugin adlarını açınca kırık-plugin senaryosu daha olası hale gelir; U2 rozeti tam o boşluğu kapatır. U3 bağımsızdır ama küçük olduğu için araya alınır. U4 en büyük parçadır ve U1'in `available_adapters`'ına dayanır. Toplam **~3–4 hafta part-time**.

## D. Kapsam Dışı (bilinçli)

- **Plugin'in kendi UI katkısı** (şablon/ekran/widget entry-point'i) — asla; arayüz her zaman core'un projeksiyonudur.
- **UI'dan kurulum/kaldırma/policy** — asla (kilitli ilke).
- **Marketplace web görünümü** (arama/tarama) — CLI-only kalır; imzalı index'in salt-okunur bir web projeksiyonu ancak Faz 5 dış repo canlanıp gerçek üçüncü-parti eklenti çıktığında backlog'dan değerlendirilir.
- **`etki.mcp_tools` UI listesi** — MCP-only yüzey; Eklentiler ekranına tool sayısı rozeti ancak gerçek talep gelirse.
- **code_repo / documents / llm portları için form üretimi** — U4 work_items'ta kalıbı kurar; diğer portlar aynı kalıbın mekanik tekrarı olarak ayrı iş açılır.
