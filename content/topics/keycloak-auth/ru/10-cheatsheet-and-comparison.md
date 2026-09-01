# Шпаргалка и сравнение

Справочный материал по статьям 01-09 — без нового объяснения концепций, только компактные таблицы и сниппеты. Если формулировка непонятна — она разобрана подробно в соответствующей статье, указанной в заголовке раздела.

## Часть 1: Шпаргалка

### Выбор grant type (статья 01)

| Клиент | Grant Type | Есть пользователь? | Может хранить секрет? | Статус |
|---|---|---|---|---|
| React SPA (single-page application, одностраничное приложение) / мобильное приложение | Authorization Code + PKCE (Proof Key for Code Exchange) | Да | Нет (public client) | ✅ актуален |
| Backend, вызывающий Keycloak от имени пользователя | Authorization Code + PKCE (здесь PKCE не обязателен, но рекомендован всегда) | Да | Да (confidential) | ✅ актуален |
| Сервис A → Сервис B (без пользователя) | Client Credentials | Нет | Да (confidential) | ✅ актуален |
| Любое устройство без удобного ввода: смарт-телевизор, консоль, CLI (command-line interface) | Device Code | Да (на **другом** устройстве) | Нет | ✅ актуален |
| ~~Форма логина внутри клиента~~ | ~~ROPC (Resource Owner Password Credentials)~~ | Да | Не важно | ❌ deprecated |
| ~~Токен в URL fragment~~ | ~~Implicit~~ | Да | Нет | ❌ deprecated |

### JWT claims Keycloak-токена (статьи 01-03)

JWT расшифровывается как JSON Web Token — подписанный самоописывающийся формат токена, который выдаёт Keycloak.

| Claim | Значение | Где встречается |
|---|---|---|
| `iss` | Issuer — URL того realm, который выдал токен | Access, ID, Refresh |
| `sub` | Subject — уникальный ID пользователя (или service account) | Access, ID |
| `aud` | Audience — для кого предназначен токен | Access, ID |
| `azp` | Authorized party — client_id, которому выдан токен | Access, ID |
| `exp` / `iat` | Expiry / issued-at (Unix timestamp) | Access, ID, Refresh |
| `jti` | JWT ID — уникальный идентификатор токена (для revoke/blacklist) | Access, ID |
| `sid` | Session ID — связывает токен с server-side сессией Keycloak | Access, ID |
| `acr` | Authentication Context Class Reference — уровень доверия к аутентификации (статья 08, step-up) | Access, ID |
| `realm_access.roles` | Realm roles (статья 02) | Access |
| `resource_access.<client>.roles` | Client roles конкретного клиента (статья 02) | Access |
| `scope` | Список выданных OAuth2-scope | Access |
| `email`, `name`, `preferred_username` | Identity claims (из scope `profile`/`email`) | ID (и Access, если сконфигурировано) |
| `nonce` | Значение для replay-защиты ID Token (статья 07) | ID |

### keycloak-js — основные методы (статья 05)

| Метод | Назначение |
|---|---|
| `new Keycloak(config)` | Создать инстанс адаптера (url, realm, clientId) |
| `keycloak.init(options)` | Инициализация; `onLoad: 'check-sso' \| 'login-required'` |
| `keycloak.login(options?)` | Редирект на Keycloak login; `redirectUri` — куда вернуться |
| `keycloak.logout(options?)` | Редирект на Keycloak logout (front-channel) |
| `keycloak.updateToken(minValidity)` | Обновить токен, если осталось < minValidity секунд; не делает запрос, если токен свежий |
| `keycloak.token` / `keycloak.tokenParsed` | Текущий access token (сырой JWT / распарсенный payload) |
| `keycloak.loadUserProfile()` | Запрос профиля пользователя (через Keycloak Account API) |
| `keycloak.hasRealmRole(role)` / `hasResourceRole(role, client)` | Проверка ролей на клиенте (не заменяет проверку на backend!) |
| `keycloak.authenticated` | Булево — залогинен ли пользователь после `init()` |

### PKCE — минимальный сниппет генерации (статья 07)

```typescript
function base64UrlEncode(buffer: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64UrlEncode(array.buffer);
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return base64UrlEncode(digest);
}
```

### NestJS — минимальный JWT-guard через JWKS (статьи 03-04)

JWKS — это JSON Web Key Set: публичные ключи, которые Keycloak публикует, чтобы подпись мог проверить кто угодно.

```typescript
export class KeycloakJwtStrategy extends PassportStrategy(Strategy, 'jwt') {
  constructor(config: ConfigService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      algorithms: ['RS256'], // всегда захардкожен — см. статью 07, algorithm confusion
      secretOrKeyProvider: passportJwtSecret({
        jwksUri: `${config.get('KEYCLOAK_ISSUER')}/protocol/openid-connect/certs`,
        cache: true,
        rateLimit: true,
      }),
      issuer: config.get('KEYCLOAK_ISSUER'),
    });
  }
  validate(payload: KeycloakJwtPayload) {
    return payload;
  }
}
```

### BFF — request flow одной схемой (статья 06)

BFF расшифровывается как Backend-for-Frontend.

```txt
Браузер  ──(first-party session cookie)──►  BFF

BFF      ──(Auth Code + PKCE, back-channel)──►  Keycloak
              client_secret лежит здесь

BFF      ──(хранит access/refresh токены в Redis или
              базе данных, ключ — sessionId)

BFF      ──(проксирует запрос: Authorization: Bearer
              <реальный токен>)──► Resource Server

Браузер никогда не видит access, refresh и ID token.
```

## Часть 2: Сравнение

Пять фактов на каждый вариант: для чего он, что делает, где применяется, какова его защищённость и во что он обходится в эксплуатации.

### Auth Code + PKCE

- **Для чего:** интерактивный логин пользователя.
- **Что делает:** отдаёт code через front-channel, меняет его на токены по back-channel и проверяет `code_verifier`.
- **Типичное применение:** любой клиент с браузером или UI (user interface, интерфейс) — SPA, мобильное приложение, серверный веб-апп.
- **Защищённость:** высокая — защищён от перехвата code независимо от типа клиента.
- **Операционная стоимость:** низкая — встроен в любую нормальную библиотеку OIDC (OpenID Connect).

### Client Credentials

- **Для чего:** вызовы сервис-сервис, без пользователя.
- **Что делает:** прямой back-channel обмен `client_id` и секрета на токен.
- **Типичное применение:** внутренние микросервисы, cron-джобы, интеграции без человека.
- **Защищённость:** высокая при условии, что `client_secret` защищён — секрет-менеджер, а не переменная окружения в коде.
- **Операционная стоимость:** низкая — один HTTP-запрос плюс кэш токена.

### Device Code

- **Для чего:** устройства с ограниченным вводом.
- **Что делает:** опрашивает сервер в ожидании токена, пока пользователь логинится на **другом** устройстве.
- **Типичное применение:** смарт-телевизоры, консоли, CLI-инструменты.
- **Защищённость:** высокая — пароль никогда не вводится на самом устройстве.
- **Операционная стоимость:** средняя — нужен механизм опроса и UX (user experience) для показа кода.

### BFF Pattern

- **Для чего:** убрать токены из браузера архитектурно.
- **Что делает:** держит server-side сессию и проксирует запросы к Resource Server с реальным токеном.
- **Типичное применение:** fintech, healthcare, enterprise-приложения с высокими ставками на безопасность.
- **Защищённость:** максимальная для браузерных сценариев — XSS (cross-site scripting) не может украсть токен.
- **Операционная стоимость:** высокая — ещё один серверный компонент, задержка, ещё одна критичная цель атаки.

### Public client в браузере

- **Для чего:** прямое обращение SPA к API.
- **Что делает:** хранит токен в браузере (память или cookie) и прикрепляет его к запросам.
- **Типичное применение:** MVP (minimum viable product), внутренние инструменты, приложения с невысокими ставками.
- **Защищённость:** средняя — компромисс между XSS, CSRF (Cross-Site Request Forgery) и UX, разобран в статье 06.
- **Операционная стоимость:** низкая — SPA может быть чисто статическим хостингом.

### Keycloak

- **Для чего:** self-hosted Identity Provider на OIDC/OAuth2.
- **Что делает:** даёт полную объектную модель — realms, clients, roles, Authorization Services.
- **Типичное применение:** компании с выделенной платформенной командой и жёсткими требованиями к compliance и размещению данных.
- **Защищённость:** настолько высокая, насколько дисциплинированно команда его эксплуатирует.
- **Операционная стоимость:** высокая — HA (high availability, высокая доступность), патчинг, апгрейды, мониторинг (статья 08).

### Auth0

- **Для чего:** managed identity-as-a-service.
- **Что делает:** даёт готовый UI, Actions и Rules для кастомизации и широкий охват SDK (software development kit).
- **Типичное применение:** стартапы и продукты, где важна скорость выхода на рынок.
- **Защищённость:** высокая, обслуживается провайдером.
- **Операционная стоимость:** биллинг по MAU (monthly active users) — низкий на старте, может резко расти с масштабом.

### Okta

- **Для чего:** managed identity с исторической силой в enterprise и workforce identity.
- **Что делает:** глубоко интегрируется с корпоративными системами SSO (single sign-on, единый вход).
- **Типичное применение:** enterprise B2E (business-to-employee), компании с существующей Okta-инфраструктурой.
- **Защищённость:** высокая, обслуживается провайдером.
- **Операционная стоимость:** биллинг по MAU или по местам, enterprise-контракты.

### AWS Cognito

- **Для чего:** managed identity с глубокой интеграцией в экосистему AWS (Amazon Web Services).
- **Что делает:** User Pools плюс Identity Pools, с Lambda triggers для кастомизации.
- **Типичное применение:** продукты, уже полностью построенные на AWS.
- **Защищённость:** высокая, обслуживается AWS.
- **Операционная стоимость:** биллинг по MAU, обычно дешевле Auth0 или Okta на объёме.

### Supabase Auth

- **Для чего:** managed или self-hostable простой старт.
- **Что делает:** GoTrue — упрощённая OIDC-подобная аутентификация как часть стека Supabase.
- **Типичное применение:** MVP, небольшие и средние проекты на Supabase.
- **Защищённость:** средняя-высокая для стандартных сценариев, без enterprise-глубины Keycloak.
- **Операционная стоимость:** низкая — минимальная конфигурация.

### Самописная auth

- **Для чего:** полный контроль и ноль зависимостей.
- **Что делает:** своя таблица users, свой код выдачи JWT, свой bcrypt.
- **Типичное применение:** крайне редко оправдано для нового проекта в 2024 году и позже.
- **Защищённость:** целиком на вашей команде — MFA (multi-factor authentication, многофакторная аутентификация), rate limiting и security best practices пишутся и поддерживаются вручную.
- **Операционная стоимость:** скрытая и постоянно растущая. Каждая security-фича, которую Keycloak или Auth0 дают из коробки, здесь пишется и поддерживается руками.
