# Шпаргалка и сравнение

Справочный материал по статьям 01-09 — без нового объяснения концепций, только компактные таблицы и сниппеты. Если формулировка непонятна — она разобрана подробно в соответствующей статье, указанной в заголовке раздела.

## Часть 1: Шпаргалка

### Выбор grant type (статья 01)

| Клиент | Grant Type | Есть пользователь? | Может хранить секрет? |
|---|---|---|---|
| React SPA / мобильное приложение | Authorization Code + PKCE | Да | Нет (public client) |
| Backend, вызывающий Keycloak от имени пользователя | Authorization Code + PKCE (или без PKCE, если хочется — но PKCE рекомендован всегда) | Да | Да (confidential) |
| Сервис A → Сервис B (без пользователя) | Client Credentials | Нет | Да (confidential) |
| Smart TV / CLI / устройство без удобного ввода | Device Code | Да (на ДРУГОМ устройстве) | Нет |
| ~~Форма логина внутри клиента~~ | ~~ROPC (password)~~ | Да | Не важно | ❌ deprecated |
| ~~Токен в URL fragment~~ | ~~Implicit~~ | Да | Нет | ❌ deprecated |

### JWT claims Keycloak-токена (статьи 01-03)

| Claim | Значение | Где встречается |
|---|---|---|
| `iss` | Issuer — URL realm'а, выдавшего токен | Access, ID, Refresh |
| `sub` | Subject — уникальный ID пользователя (или service account) | Access, ID |
| `aud` | Audience — для кого предназначен токен | Access, ID |
| `azp` | Authorized party — client_id, которому выдан токен | Access, ID |
| `exp` / `iat` | Expiry / issued-at (UNIX timestamp) | Access, ID, Refresh |
| `jti` | JWT ID — уникальный идентификатор токена (для revoke/blacklist) | Access, ID |
| `sid` | Session ID — связывает токен с server-side сессией Keycloak | Access, ID |
| `acr` | Authentication Context Class Reference — уровень доверия к аутентификации (статья 08, step-up) | Access, ID |
| `realm_access.roles` | Realm roles (статья 02) | Access |
| `resource_access.<client>.roles` | Client roles конкретного клиента (статья 02) | Access |
| `scope` | Список выданных OAuth2 scope'ов | Access |
| `email`, `name`, `preferred_username` | Identity claims (из scope `profile`/`email`) | ID (и Access, если сконфигурировано) |
| `nonce` | Значение для replay-защиты ID Token'а (статья 07) | ID |

### keycloak-js — основные методы (статья 05)

| Метод | Назначение |
|---|---|
| `new Keycloak(config)` | Создать инстанс адаптера (url, realm, clientId) |
| `keycloak.init(options)` | Инициализация; `onLoad: 'check-sso' \| 'login-required'` |
| `keycloak.login(options?)` | Редирект на Keycloak login; `redirectUri` — куда вернуться |
| `keycloak.logout(options?)` | Редирект на Keycloak logout (front-channel) |
| `keycloak.updateToken(minValidity)` | Обновить токен, если осталось < minValidity секунд; не делает запрос, если токен свежий |
| `keycloak.token` / `keycloak.tokenParsed` | Текущий access token (сырой JWT / распарсенный payload) |
| `keycloak.loadUserProfile()` | Запрос профиля пользователя (через Keycloak Account REST API) |
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

```typescript
export class KeycloakJwtStrategy extends PassportStrategy(Strategy, 'jwt') {
  constructor(config: ConfigService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      algorithms: ['RS256'], // ВСЕГДА захардкожен — см. статью 07, algorithm confusion
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

```txt
Браузер ──(first-party session cookie)──► BFF
BFF ──(Auth Code+PKCE, back-channel, client_secret ЗДЕСЬ)──► Keycloak
BFF ──(access/refresh token хранятся в Redis/БД, keyed by sessionId)
BFF ──(проксирует запрос, Authorization: Bearer <реальный токен>)──► Resource Server

Браузер НИКОГДА не видит access/refresh/ID token.
```

## Часть 2: Сравнение

| | Для чего | Что делает | Типичное применение | Security posture | Операционная стоимость |
|---|---|---|---|---|---|
| **Auth Code + PKCE** | Интерактивный логин пользователя | Code через front-channel, обмен на токены через back-channel + верификация code_verifier | Любой клиент с браузером/UI: SPA, мобильное приложение, серверный веб-апп | Высокая — защищён от code interception независимо от типа клиента | Низкая — встроен в любую нормальную OIDC-библиотеку |
| **Client Credentials** | Service-to-service, без пользователя | Прямой back-channel обмен client_id+secret на токен | Внутренние микросервисы, cron-джобы, интеграции без человека | Высокая, при условии защиты client_secret (секрет-менеджер, не env в коде) | Низкая — один HTTP-запрос + кэш токена |
| **Device Code** | Устройства с ограниченным вводом | Polling токена, пока пользователь логинится на ДРУГОМ устройстве | Smart TV, консоли, CLI-инструменты | Высокая — пароль никогда не вводится на самом устройстве | Средняя — нужен polling-механизм и UX для отображения кода |
| **BFF Pattern** | Убрать токены из браузера архитектурно | Server-side session + прокси к Resource Server с реальным токеном | Fintech, healthcare, enterprise-приложения с высокими ставками на безопасность | Максимальная для браузерных сценариев — XSS не может украсть токен | Высокая — доп. serverful-компонент, latency, доп. критичная цель атаки |
| **Public client в браузере** | Прямое обращение SPA к API | Токен хранится в браузере (память/cookie), прикрепляется к запросам | MVP, внутренние инструменты, low-stakes приложения | Средняя — компромисс между XSS/CSRF/UX, разобран в статье 06 | Низкая — SPA может быть чисто статическим хостингом |
| **Keycloak** | Self-hosted OIDC/OAuth2 Identity Provider | Полная объектная модель (realms, clients, roles, Authorization Services) | Компании с dedicated platform-командой, строгие compliance/data residency требования | Настолько высокая, насколько правильно эксплуатируется командой | Высокая — HA, патчинг, апгрейды, мониторинг (статья 08) |
| **Auth0** | Managed identity-as-a-service | Готовый UI, Actions/Rules для кастомизации, широкий SDK-охват | Стартапы и продукты, где важна скорость выхода на рынок | Высокая, обслуживается провайдером | MAU-биллинг — низкая на старте, может резко расти с масштабом |
| **Okta** | Managed, историческая сила в enterprise/workforce identity | Глубокая интеграция с корпоративными SSO-системами | Enterprise B2E, компании с существующей Okta-инфраструктурой | Высокая, обслуживается провайдером | MAU/seat-биллинг, enterprise-контракты |
| **AWS Cognito** | Managed, глубокая интеграция с AWS-экосистемой | User Pools + Identity Pools, Lambda triggers для кастомизации | Продукты, уже полностью построенные на AWS | Высокая, обслуживается AWS | MAU-биллинг, обычно дешевле Auth0/Okta на объёме |
| **Supabase Auth** | Managed/self-hostable, простой старт | GoTrue — упрощённая OIDC-подобная аутентификация как часть Supabase-стека | MVP, small-to-medium проекты на Supabase | Средняя-высокая для стандартных сценариев, без enterprise-глубины Keycloak | Низкая — минимальная конфигурация |
| **Самописная auth** | Полный контроль, ноль зависимостей | Своя таблица users, свой JWT-issuing код, свой bcrypt | Крайне редко оправдано для нового проекта в 2024+ | Целиком на вашей команде — MFA/rate-limiting/security best practices нужно реализовать и поддерживать самим | Скрытая и постоянно растущая — каждая security-фича, которую дают Keycloak/Auth0 "из коробки", здесь пишется и поддерживается вручную |
