# Keycloak — объектная модель

Эта статья — карта объектной модели Keycloak: Realm, Client, User, Role, Group, Client Scope. В статьях 04 и 05 к этой карте привязывается конкретный код NestJS и React.

Keycloak — это не "чёрный ящик, который выдаёт JSON Web Token (JWT)". Это сервер OpenID Connect (OIDC) с довольно строгой объектной моделью. Без понимания этой модели конфигурация Keycloak превращается в клики по админке методом тыка. И любая непонятная проблема в проде расследуется на ощупь: в токене нет нужного claim, пользователь из LDAP (Lightweight Directory Access Protocol) не может залогиниться.

## Realm — изолированный "тенант" внутри одного Keycloak

**Realm** — это полностью изолированное пространство. У него свои пользователи, клиенты, роли и темы, плюс свои настройки безопасности: политика паролей, brute-force protection, время жизни токенов (TTL). Два realm на одном инстансе Keycloak не видят данные друг друга вообще. Как будто это два разных Keycloak-сервера, физически развёрнутых на одном хосте.

```txt
┌────────────────────────────────────────────────┐
│ Keycloak instance                              │
├────────────────────────────────────────────────┤
│ Realm "acme-internal"                          │
│   Users: сотрудники компании                   │
│   Clients: internal-admin-panel, hr-service    │
│   Password policy: строгая, MFA обязателен     │
├────────────────────────────────────────────────┤
│ Realm "acme-customers"                         │
│   Users: клиенты продукта                      │
│   Clients: customer-web-app, mobile-app        │
│   Password policy: мягче, social login включён │
└────────────────────────────────────────────────┘
```

Realm — это единица, на уровне которой принимается решение: отдельные realm под каждого тенанта или общий realm с группами. Полный разбор компромиссов — в статье [Advanced Patterns](./08-advanced-patterns.md). Здесь фиксируем сам факт: Realm физически **может** быть границей тенанта, но не обязан ею быть.

Отдельный realm существует всегда — `master`, создаваемый по умолчанию при установке. **Realm `master` предназначен для администрирования самого Keycloak** — создание других realm, управление серверными настройками.

Реальные пользователи приложения никогда не должны логиниться через `master`. Частая ошибка на старте проекта — по инерции продолжать всё конфигурировать в `master`, вместо того чтобы сразу создать отдельный realm под приложение.

## Client — кто и как обращается к Keycloak

**Client** в терминах Keycloak — это регистрация конкретного приложения внутри realm. Это та самая роль "Client" из протокола OAuth2, описанная в статье [OAuth2 / OIDC Fundamentals](./01-oauth2-oidc-fundamentals.md). У клиента настраиваются разрешённые grant types, `redirect_uri` и время жизни токенов персонально для него. Самое важное для архитектуры — **тип клиента**:

|  | Может хранить секрет? | Типичный пример |
|---|---|---|
| Public | Нет | React SPA (одностраничное приложение), мобильное приложение — весь код выполняется на устройстве пользователя, секрет там не защитить |
| Confidential | Да | NestJS backend или сервис backend-for-frontend — код исполняется на сервере вашей команды, секрет можно хранить в env или secret manager |
| Bearer-only | В логине не участвует | Чисто Resource Server — API, который только **валидирует** токены, выданные другим клиентом, и никогда сам не инициирует OAuth2-флоу |

`public` в Keycloak буквально означает "у этого клиента `client_secret` пуст, и Keycloak не будет требовать его при обмене code→token". Именно поэтому для public-клиентов PKCE (Proof Key for Code Exchange) не опция, а обязательная защита. Без секрета и без PKCE обмен code→token может провести кто угодно, кто перехватил code.

`bearer-only` — тип, который часто путают с "confidential для API". Разница принципиальна. Bearer-only клиент **не имеет собственного login endpoint и не может инициировать Authorization Code flow**. Он существует только для того, чтобы в Keycloak Admin Console можно было настроить client roles для этого API и валидировать `aud` (audience) в токене.

На практике NestJS resource server часто вообще не заводят как отдельный Keycloak client. Токен, выданный для React SPA (это public client), валидируется на бэкенде напрямую через JWKS (JSON Web Key Set). Про это — статьи [Tokens, Sessions, and Validation](./03-tokens-sessions-and-validation.md) и [NestJS Resource Server](./04-nestjs-resource-server.md).

Bearer-only client нужен, когда важно явно разграничить `aud` между разными API.

```bash
# Создание confidential-клиента через Admin REST API
curl -X POST https://keycloak.example.com/admin/realms/myrealm/clients \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "backend-service",
    "publicClient": false,
    "serviceAccountsEnabled": true,
    "standardFlowEnabled": false,
    "directAccessGrantsEnabled": false
  }'
```

Обратите внимание на `serviceAccountsEnabled: true` — это флаг, включающий Client Credentials Grant для клиента. Keycloak называет это "service account". У такого клиента даже есть отдельный технический пользователь `service-account-backend-service`, которому можно назначать роли.

## Users, Groups, Roles — модель авторизации

### Realm roles vs Client roles

Роли в Keycloak бывают двух видов, и разница — не синтаксическая, а смысловая:

```txt
Realm role:
  Существует на уровне ВСЕГО realm. Пример: "admin",
  "premium-user". Имеет смысл во всех клиентах этого realm
  одновременно.
  claim в токене: realm_access.roles: ["admin", "premium-user"]

Client role:
  Существует в КОНТЕКСТЕ одного конкретного клиента. Пример:
  клиент "billing-service" может иметь роль "invoice:write",
  которая не имеет смысла ни для какого другого клиента.
  claim в токене:
    resource_access.billing-service.roles: ["invoice:write"]
```

```json
{
  "sub": "a1b2c3",
  "realm_access": {
    "roles": ["offline_access", "premium-user"]
  },
  "resource_access": {
    "billing-service": {
      "roles": ["invoice:write", "invoice:read"]
    },
    "account": {
      "roles": ["manage-account"]
    }
  }
}
```

Практическое правило выбора. Если право имеет смысл вообще для пользователя, независимо от того, каким API он сейчас пользуется, — это realm role. Если право специфично для конкретного сервиса ("может ли пользователь удалять инвойсы в billing-service") — это client role этого сервиса.

Ошибка новичков — заводить всё как realm roles, потому что "так проще". Со временем `realm_access.roles` превращается в свалку из полусотни ролей вперемешку, где непонятно, к какому сервису какая относится.

### Composite roles

**Composite role** — роль, которая при назначении пользователю автоматически "разворачивается" в набор других ролей.

```txt
Composite role "app-admin" включает в себя:
  realm role "premium-user"
  + client role billing-service:"invoice:write"
  + client role billing-service:"invoice:read"
  + client role admin-panel:"users:manage"

Назначить пользователю ОДНУ роль "app-admin" →
  в токене появятся ВСЕ 4 роли из композита автоматически
```

Composite roles моделируют "должности" и "тарифные планы" одним назначением. Иначе список из десятка отдельных ролей на каждого пользователя приходится поддерживать вручную.

Senior-нюанс: composite roles облегчают назначение, но усложняют аудит. Посмотрев на пользователя, видно только "app-admin". Полный список фактических прав нужно разворачивать отдельно — через Admin API или вкладку "Effective Roles" в консоли.

### Groups — назначение ролей пачками пользователям

**Group** — это способ назначить набор ролей (и атрибутов) сразу многим пользователям, без композитных ролей на каждого. Группы поддерживают иерархию (`/company/engineering/backend`), и роли, назначенные родительской группе, наследуются дочерними.

```txt
Group "/company/engineering"
  → realm role "internal-tool-access"

Group "/company/engineering/backend" (наследует /engineering)
  → client role backend-service:"deploy"

Пользователь в группе /company/engineering/backend получает
ОБЕ роли:
  "internal-tool-access" (унаследовано) + "deploy" (своё)
```

Разница между Group и Composite Role — частый вопрос. Composite role — это отношение "роль включает роли", оно применяется везде, где эту роль назначили. Group — это отношение "пользователь состоит в организационной единице". Группа дополнительно может нести атрибуты (`department: backend`), и её удобно администрировать по оргструктуре компании, а не по абстрактному набору прав.

## Client Scopes и Protocol Mappers — как реально устроить содержимое токена

Это тот механизм, который отвечает на вопрос "как scope из статьи 01 превращается в конкретные claims в JWT". Навык практический, он нужен почти в каждом реальном проекте: кастомные claims для бизнес-логики, например `tenantId`, `subscriptionTier` или внутренний массив `permissions`.

**Client Scope** — именованный, переиспользуемый набор конфигурации, который можно подключить к любому количеству клиентов. Стандартные scope — `profile`, `email`, `roles` — поставляются с Keycloak из коробки, а кастомные вы создаёте сами.

**Protocol Mapper** — конкретное правило внутри client scope. Оно говорит: взять вот такие данные и положить их в токен под таким-то claim-именем. Данными может быть атрибут пользователя, роль, статичное значение или скрипт.

```txt
Client Scope "tenant-info" (кастомный, создан вручную)
  └─ Protocol Mapper "tenant-id-mapper"
       Тип: "User Attribute"
       User Attribute:  tenantId
         (кастомный атрибут пользователя в Keycloak)
       Token Claim Name: tenant_id
       Add to ID token: ✓
       Add to access token: ✓
```

```bash
# Создание protocol mapper через Admin REST API —
# добавляет пользовательский атрибут tenantId как claim tenant_id
KC_REALM=https://keycloak.example.com/admin/realms/myrealm
curl -X POST \
  "$KC_REALM/client-scopes/$SCOPE_ID/protocol-mappers/models" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "tenant-id-mapper",
    "protocol": "openid-connect",
    "protocolMapper": "oidc-usermodel-attribute-mapper",
    "config": {
      "user.attribute": "tenantId",
      "claim.name": "tenant_id",
      "jsonType.label": "String",
      "id.token.claim": "true",
      "access.token.claim": "true"
    }
  }'
```

Результат в токене:

```json
{
  "sub": "a1b2c3",
  "tenant_id": "acme-corp",
  "realm_access": { "roles": ["premium-user"] }
}
```

Client Scope затем подключается к клиенту как **Default** или **Optional**. Default значит, что scope добавляется в токен автоматически при любом логине этим клиентом. Optional значит, что он добавляется только если клиент явно запросил его в параметре `scope=` при редиректе на `/authorize`.

Это прямое продолжение механики "scope запрашивает, claim появляется" из статьи 01, только теперь видно, **где** именно конфигурируется эта связь.

Практический сценарий, который стоит проговорить. Фронтенд внезапно перестал видеть нужный claim в токене — сразу после того, как кто-то "прибрался" в Keycloak и отвязал client scope от клиента. Это не баг фронтенда и не баг библиотеки, это чисто конфигурационная проблема Keycloak. Диагностика — вкладка клиента "Client Scopes": проверить, что нужный scope есть либо в Default, либо запрошен явно.

## Identity Brokering vs User Federation — пара, которую разработчики путают систематически

Оба механизма про внешний источник пользователей, и оба выглядят как "логин через что-то ещё". Но решают они принципиально разные задачи. Внешний identity provider (IdP) может говорить на OIDC или на SAML (Security Assertion Markup Language). SAML старше OIDC и передаёт свои утверждения документами XML (extensible markup language).

```txt
Identity Brokering:
  Keycloak делегирует АУТЕНТИФИКАЦИЮ внешнему Identity
  Provider (Google, GitHub, другой Keycloak, любой провайдер
  OIDC или SAML). Пользователь нажимает "Войти через Google"
  → редиректится на Google → логинится там → Google
  возвращает Keycloak токен или assertion → Keycloak создаёт
  локальную учётную запись-"тень" (linked account) в своём
  realm, привязанную к внешнему sub.

  Пароль пользователя Keycloak вообще никогда не видит.
  Кому:      "Login with Google / GitHub / корпоративный
             Azure AD"
  Ключевое:  Keycloak — это Client OAuth2-флоу по отношению
             к внешнему IdP

User Federation:
  Keycloak САМ аутентифицирует пользователя (проверяет
  пароль), но данные пользователя — и сама проверка пароля —
  живут в существующем внешнем хранилище. Обычно это LDAP
  или Active Directory, доступные через провайдер федерации:
  встроенный LDAP-провайдер либо Custom User Storage SPI
  для произвольного источника.

  Keycloak делает bind-запрос к LDAP с введённым паролем
  при логине.
  Кому:      "У компании уже есть Active Directory
             с 5000 сотрудников, Keycloak должен
             использовать ИХ учётки, а не заводить копию
             базы"
  Ключевое:  Keycloak — это "фасад" OIDC/SAML поверх
             существующего каталога пользователей
```

```txt
Identity Brokering:              User Federation:

  User → Keycloak                  User → Keycloak
    → [redirect]                     → [LDAP bind]
    → внешний IdP (Google)           → Active Directory
    (Keycloak = OAuth2 Client        (Keycloak = фасад,
     по отношению к Google)           пароль проверяется
                                      в AD)
```

Мнемоника, которая реально помогает не путать: **Identity Brokering — это "ещё одна кнопка на экране логина"**. Пользователь сам выбирает, как аутентифицироваться, и этот выбор он видит.

**User Federation — это "невидимый бэкенд"** для стандартной формы логина Keycloak. Пользователь вводит логин и пароль как обычно, просто эти данные проверяются не во внутренней базе Keycloak, а в LDAP. Их можно комбинировать: локальные пользователи, LDAP-федерация и Google-брокеринг одновременно в одном realm.

## Authentication Flows — конструктор шагов логина

**Authentication Flow** — настраиваемая последовательность шагов, через которые проходит пользователь при логине или при других действиях: сбросе пароля, регистрации. Стандартный `browser` flow уже включает три шага. Сначала проверка куки существующей сессии single sign-on (SSO), потом форма логина, потом — опционально — проверка одноразового пароля (OTP).

У каждого шага есть требование:

- **Required** — обязателен.
- **Alternative** — один из нескольких равноправных вариантов, например пароль или WebAuthn.
- **Conditional** — выполняется только при выполнении условия, например "если у пользователя есть роль admin, требовать OTP".

```txt
Пример кастомного flow "Login with conditional OTP":

  Cookie (проверка SSO-сессии)        [ALTERNATIVE]
  Username Password Form              [REQUIRED]
  └─ Condition: user has role "admin" [CONDITIONAL]
      └─ OTP Form                     [REQUIRED внутри условия]
```

Это прямой механизм для step-up-аутентификации. Не глобальная многофакторная аутентификация (MFA) для всех, а точечное требование второго фактора для конкретных ролей, групп или клиентов. Настраивается декларативно в конструкторе flow, без единой строчки кода в самом приложении. Детальные сценарии — в статье [Advanced Patterns](./08-advanced-patterns.md).

## Themes — кастомизация экрана логина

**Theme** — набор FreeMarker-шаблонов плюс CSS и JS. Он определяет внешний вид страниц, которые рендерит сам Keycloak: login, registration, email-шаблоны, error pages.

Важный архитектурный факт: страница логина — это **страница самого Keycloak**, а не вашего React-приложения. Пользователь физически покидает домен SPA на время аутентификации. Это часть модели безопасности Authorization Code flow: фронтенд-код никогда не должен получить пароль в руки.

```txt
┌──────────────────────────────────────────────┐
│ app.example.com — ваш React SPA              │
└──────────────────────────────────────────────┘
                        │  редирект на /authorize
                        ▼
┌──────────────────────────────────────────────┐
│ keycloak.example.com — Keycloak сам рендерит │
│ страницу логина, по Theme                    │
└──────────────────────────────────────────────┘
                        │  редирект обратно с code
                        ▼
┌──────────────────────────────────────────────┐
│ app.example.com — SPA продолжает работу      │
└──────────────────────────────────────────────┘
```

Theme — это способ сделать так, чтобы эта чужая, но обязательная страница выглядела брендированной, а не как дефолтная админка Keycloak.

## Admin REST API и Keycloak-as-Code — операционная зрелость

Всё, что показано выше через `curl`, доступно и через полноценный **Admin REST API**. Это интерфейс в стиле REST (representational state transfer), то есть обычный HTTP API. Keycloak управляется через тот же механизм OAuth2/OIDC: для вызова admin API нужен access token сервисного клиента с нужными admin-ролями.

Кликать конфигурацию realm вручную в консоли нормально для одного дев-стенда. Но это не масштабируется на "дев + стейджинг + прод + временные окружения для feature-веток". Конфигурация неизбежно расходится, и через полгода никто не может ответить, почему в проде другая политика паролей, чем в стейджинге.

Senior-практика — **realm-as-code**: держать всю конфигурацию realm (клиенты, роли, client scopes, flows) в виде декларативных файлов в git, применяемых автоматически:

```txt
keycloak-config-cli:
  Утилита (Java, от adorsys), которая принимает описание realm
  в YAML или JSON и идемпотентно приводит реальный Keycloak
  к этому состоянию через Admin REST API. Можно гонять
  в CI/CD при каждом деплое.

Keycloak Terraform Provider (mrparkers/keycloak или
                             актуальный keycloak/keycloak):
  Тот же принцип, но в терминах Terraform-ресурсов
  (keycloak_realm, keycloak_openid_client, keycloak_role).
  Удобно, если вся остальная инфраструктура уже описана
  в Terraform: даёт plan/apply-цикл и явный diff перед
  применением изменений.
```

```yaml
# Фрагмент конфигурации keycloak-config-cli
realm: myrealm
clients:
  - clientId: backend-service
    publicClient: false
    serviceAccountsEnabled: true
    standardFlowEnabled: false
roles:
  realm:
    - name: premium-user
      description: "Access to premium features"
```

Это не бюрократия ради бюрократии. Realm — источник истины для авторизации всей системы. Если он настраивается кликами без версионирования, откат неудачного изменения превращается в расследование по памяти, а не в `git revert`. Типичное такое изменение: кто-то случайно снял service account у продового клиента.

## Итоговая связь понятий

```txt
[Realm]                  →  изолированная граница
                            конфигурации; решение
                            "realm-per-tenant vs shared" —
                            архитектурный выбор
                            (Advanced Patterns)

[Client type]            →  public / confidential /
                            bearer-only определяется тем,
                            может ли клиент безопасно
                            хранить секрет

[Realm role / Client
 role / Composite /
 Group]                  →  четыре способа моделирования
                            "что разрешено", каждый для
                            своей гранулярности

[Client Scope +
 Protocol Mapper]        →  механизм, превращающий scope
                            в конкретные claims токена —
                            то, что нужно настроить для
                            любого кастомного поля в JWT

[Identity Brokering vs
 User Federation]        →  "внешний IdP делает
                            аутентификацию" vs "внешний
                            каталог хранит пароли, которые
                            Keycloak сам проверяет"

[Authentication Flows]   →  конструктор шагов логина —
                            декларативный step-up без кода

[Realm-as-code]          →  операционная зрелость:
                            конфигурация Keycloak как часть
                            git-репозитория, а не кликов
                            в консоли
```

Следующая статья, [Tokens, Sessions, and Validation](./03-tokens-sessions-and-validation.md), переходит от "как настроен Keycloak" к тому, что происходит с уже выданным токеном на стороне API. Там разбирается, как токен валидируется и что такое JWKS и `kid`. И там же — logout в системе, где сессия существует и на Keycloak, и, по факту, на клиенте.

## Типичные ошибки на интервью

- **"Realm — это просто папка для организации клиентов"** — недооценка. Realm — это полная изоляция: пользователи, политики паролей, brute-force protection, темы. Это не просто namespace для группировки. Два клиента в разных realm не могут напрямую переиспользовать роли или пользователей друг друга без явного Identity Brokering между realm.

- **"Bearer-only client — это то же самое, что confidential client для API"** — нет. Confidential client **может** инициировать флоу, например Client Credentials для связи между сервисами. Bearer-only не может инициировать OAuth2-флоу вообще. Он только валидирует чужие токены и существует ради явного разграничения ролей и audience для конкретного API.

- **"Identity Brokering и User Federation — это одно и то же, просто разные названия для 'логина через LDAP/Google'"** — фундаментальная путаница. Brokering: Keycloak сам ничего не проверяет, он редиректит на внешний identity provider с OIDC или SAML. Federation: Keycloak сам проверяет пароль, например через LDAP bind. Просто источник данных — внешний каталог, а не встроенная база.

- **"Composite role и Group — взаимозаменяемые способы группировки прав"** — нет. Composite role — это свойство самой роли: она разворачивается при любом назначении, где угодно. Group — это оргединица с собственной иерархией и атрибутами, к которой можно привязать пользователей и роли. У них разная семантика администрирования, даже если итоговый набор прав пользователя может выглядеть одинаково.

- **"Claims в токене можно менять только через код бэкенда"** — нет. Это распространённая ошибка людей, не знакомых с Protocol Mappers. Добавление кастомного claim, например `tenant_id`, — это конфигурация Keycloak: Client Scope плюс Protocol Mapper, а не код на стороне API. Писать для этого код означало бы решать задачу не на том уровне архитектуры.
