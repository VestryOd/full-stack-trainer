# NestJS как Resource Server

## От "валидируем токен" к "правильно спроектированному API"

Эта статья превращает механику статьи 03 в конкретную архитектуру NestJS-приложения. Статья 03 объяснила JWKS (JSON Web Key Set), `kid`, локальную валидацию против introspection и то, кто отвечает за refresh.

Здесь мы отвечаем на четыре вопроса. Какой Guard что проверяет? Как роли Keycloak превращаются в решения `@Roles('admin')`? Что делать, когда простого "есть роль / нет роли" недостаточно? И как сервисы говорят друг с другом, когда пользователя нет вообще?

## Ручной подход vs адаптер — осознанный выбор, а не "что нашлось в гугле"

Есть два реалистичных пути подключить NestJS к Keycloak. Выбор между ними — архитектурное решение с конкретными компромиссами, а не вопрос вкуса.

```txt
Ручной подход (passport-jwt + jwks-rsa):
  Вы сами пишете JwtStrategy (см. статью 03), сами пишете Guards
  и декораторы для ролей, сами решаете, что делать с каждым
  claim в токене.

  ✓ Полная прозрачность: видно каждую строчку, которая принимает
    решение "пустить/не пустить" — критично для аудита безопасности
  ✓ Не тянет зависимость, специфичную для Keycloak, в основной код —
    легче было бы переехать на другой OIDC-провайдер
  ✓ Полный контроль над форматом ошибок, над логированием и над
    тем, какие claims извлекаются и как
  ✗ Больше кода для написания и поддержки самостоятельно
  ✗ Легко забыть тонкость (например, проверку audience) — за вас
    её никто не проверит

Адаптер (nest-keycloak-connect / keycloak-connect):
  Официальный (или community) NestJS-модуль, обёртывающий
  Keycloak-специфичные Guards, декораторы (@Roles, @Public,
  @AuthenticatedUser), интеграцию с Keycloak Authorization
  Services "из коробки".

  ✓ Меньше кода — Guards и декораторы уже написаны и протестированы
  ✓ "Из коробки" поддержка resource-based авторизации (Keycloak
    Authorization Services), которую вручную реализовывать дольше
  ✗ Меньше прозрачности — часть логики валидации скрыта внутри
    библиотеки, при отладке нужно читать её исходники
  ✗ Тесная связка с Keycloak конкретно — если через год решат
    мигрировать на Auth0/Okta, слой абстракции придётся выстраивать
    заново, а не просто заменить issuer URL
  ✗ Зависимость от поддержки community-пакета (не всегда официальный
    Red Hat/Keycloak модуль, важно проверять активность репозитория)
```

Практическая рекомендация: **для собственного продукта, который точно останется на Keycloak надолго и которому нужны Authorization Services, адаптер оправдан**.

Ручной подход — для API, где важна максимальная прозрачность: fintech, что угодно с внешним аудитом безопасности. То же самое, если команда хочет сохранить возможность сменить провайдера. Оба подхода стоят на одном протокольном фундаменте из статей 01-03. Разница только в том, кто пишет код Guards: вы или библиотека.

## Guards и декораторы — маппинг ролей Keycloak на авторизацию NestJS

Пишете сами или берёте адаптер — итоговая архитектура одинакова. **Guard проверяет токен и извлекает роли. Декоратор на контроллере объявляет требование. Reflector связывает эти две части.**

```typescript
// roles.decorator.ts — метаданные требуемых ролей на хендлере/контроллере
import { SetMetadata } from '@nestjs/common';

export const ROLES_KEY = 'roles';
export const Roles = (...roles: string[]) => SetMetadata(ROLES_KEY, roles);
```

```typescript
// roles.guard.ts — читает realm_access.roles из payload, сравнивает с метаданными
import {
  CanActivate, ExecutionContext, ForbiddenException, Injectable,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<string[]>(ROLES_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    // роль не требуется — открыт любому аутентифицированному
    if (!requiredRoles?.length) return true;

    const { user } = context.switchToHttp().getRequest();
    const realmRoles: string[] = user?.realm_access?.roles ?? [];

    const hasRole = requiredRoles.some((role) => realmRoles.includes(role));
    if (!hasRole) {
      throw new ForbiddenException({
        error: 'insufficient_role',
        required: requiredRoles,
      });
    }
    return true;
  }
}
```

```typescript
// billing.controller.ts — декларативное требование роли на конкретном эндпоинте
@Controller('invoices')
@UseGuards(AuthGuard('jwt'), RolesGuard) // сначала аутентификация, потом авторизация
export class InvoicesController {
  @Post()
  @Roles('billing-service:invoice:write') // client role из статьи 02
  async create(@Body() dto: CreateInvoiceDto) { /* ... */ }

  @Get()
  @Roles('billing-service:invoice:read')
  async findAll() { /* ... */ }
}
```

Ключевой архитектурный момент, который часто упускают: **`AuthGuard('jwt')` и `RolesGuard` — это два разных Guard, выполняющихся один за другим.** Это не один слитный Guard. `AuthGuard('jwt')` — аутентификация, "кто это". `RolesGuard` — авторизация, "что ему разрешено".

Разделение важно: оно позволяет переиспользовать `RolesGuard` для других способов аутентификации, например для API-ключа внутренних сервисов, без дублирования логики проверки ролей.

Для client roles (`resource_access.billing-service.roles`, см. статью 02) декоратор и Guard пишутся аналогично. Они просто читают другой путь в payload. На практике удобно сделать один универсальный `@RequireRole(type: 'realm' | 'client', clientId?: string, role: string)`. Но переусложнять этот API не стоит, если в проекте реально используются либо только realm roles, либо только client roles одного сервиса.

```txt
       Два Guard, выполняющихся один за другим
┌───────────────────────────────────────────────────┐
│ Запрос с заголовком Authorization: Bearer <token> │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ AuthGuard('jwt')  —  аутентификация               │
│ отвечает на "кто это"                             │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ RolesGuard        —  авторизация                  │
│ отвечает на "что ему разрешено"                   │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ Роль из @Roles(...) совпала: метод работает       │
└───────────────────────────────────────────────────┘
    RolesGuard переиспользуем: заменяете AuthGuard
      на Guard с API-ключом, логика ролей та же
```

## Когда простых ролей не хватает — Keycloak Authorization Services

Role-based проверка ("есть роль admin — можно всё, нет — нельзя ничего") отлично работает, пока правила статичны. Она перестаёт работать для правил вида "пользователь может редактировать **только свои** документы". Или "доступ к ресурсу зависит от времени суток и от отдела, в котором состоит пользователь".

Это уже не авторизация по роли. Это авторизация по **атрибутам ресурса и контексту**, и Keycloak даёт для неё отдельный слой: **Authorization Services**, UMA-подобная модель (User-Managed Access).

```txt
Объектная модель Authorization Services:

  Resource   — конкретная защищаемая сущность или тип сущностей
               ("Invoice", "Document:42", "/admin/*")
  Scope      — действие над ресурсом ("view", "edit", "delete").
               Не путать с OAuth2 scope из статьи 01: здесь это
               просто имя действия внутри Authorization Services
  Policy     — правило принятия решения: role-based policy,
               time-based policy, JS-based policy (своя логика),
               group-based policy, client-based policy...
  Permission — связывает Resource + Scope с одной или несколькими
               Policy: "Permission 'edit-invoice' разрешена, если
               выполняется Policy 'owner-only' или 'admin-role'"
```

```txt
Policy Enforcement Point (PEP) — паттерн, а не Keycloak-термин:

  Resource Server (NestJS) НЕ реализует бизнес-правила авторизации
  сам — вместо этого на каждый защищённый запрос он спрашивает
  Keycloak (Policy Decision Point): "может ли этот пользователь
  выполнить scope 'edit' над resource 'Invoice:42'?"

  NestJS API                     Keycloak (PDP)
  ────────────                   ──────────────
  PUT /invoices/42     ──────►   UMA Permission Ticket /
  (PEP: перехватывает     RPT     Token endpoint:
   запрос, спрашивает      ◄──────  "invoice:42#edit" → RESOLVED
   разрешение)                     (или DENIED)
```

```bash
# UMA-подобный запрос на проверку разрешения — RPT (Requesting Party Token)
curl -X POST \
  https://keycloak.example.com/realms/myrealm/protocol/openid-connect/token \
  -H "Authorization: Bearer $USER_ACCESS_TOKEN" \
  -d "grant_type=urn:ietf:params:oauth:grant-type:uma-ticket" \
  -d "audience=billing-service" \
  -d "permission=Invoice:42#edit"
```

```json
// Ответ при разрешённом доступе — RPT содержит authorization claim
{
  "access_token": "eyJhbGci...",
  "token_type": "Bearer"
}
// Payload RPT внутри содержит:
// "authorization": { "permissions": [{ "rsid": "invoice-42-id", "scopes": ["edit"] }] }
```

```typescript
// NestJS: guard, делегирующий решение Keycloak вместо локальной проверки роли
@Injectable()
export class UmaPermissionGuard implements CanActivate {
  constructor(
    private reflector: Reflector,
    private keycloakAuth: KeycloakAuthorizationService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest();
    const resource = this.reflector.get<string>('resource', context.getHandler());
    const scope = this.reflector.get<string>('scope', context.getHandler());

    const allowed = await this.keycloakAuth.checkPermission(
      req.headers.authorization, // access token пользователя
      `${resource}#${scope}`,
    );
    if (!allowed) throw new ForbiddenException('uma_permission_denied');
    return true;
  }
}
```

Когда стоит переходить на Authorization Services, а когда — нет:

```txt
Достаточно простых ролей:
  - Правила статичны и не зависят от конкретного экземпляра ресурса
  - "Кто угодно с ролью X может делать Y с любым ресурсом типа"
  - Небольшая команда, которой важна простота отладки без похода
    в Keycloak Admin Console за конфигом Policy

Нужны Authorization Services:
  - Правила зависят от конкретного экземпляра ресурса (владение,
    атрибуты записи в базе) или от контекста (время, IP, атрибуты
    пользователя за пределами ролей)
  - Бизнес хочет управлять правилами доступа без участия
    разработчиков (нетехнический специалист по безопасности
    настраивает Policy через Keycloak Admin Console)
  - Нужен централизованный аудит "кто, что, когда мог делать" —
    Keycloak логирует permission-запросы в одном месте
```

Честная оговорка: Authorization Services добавляют сетевой round-trip на каждую проверку, если не кэшировать RPT (Requesting Party Token). Плюс когнитивная нагрузка — команде нужно понимать модель Resource/Scope/Policy/Permission, а не просто читать `if (user.roles.includes(...))`.

Для большинства CRUD-приложений (create, read, update, delete) модель владения — это "мои записи против чужих". Часто достаточно проверить `resource.ownerId === user.sub` прямо в коде сервиса. Не всякая проверка владения обязана идти через UMA — только сложные правила и те, которым нужна централизованная политика, редактируемая без деплоя.

## Монолит vs API Gateway — где именно валидировать токен в микросервисной архитектуре

Это архитектурный выбор, влияющий на весь стек, а не деталь одного сервиса.

```txt
Вариант A — каждый сервис валидирует токен самостоятельно:

  Client → Service A (валидирует JWT через JWKS)
         → Service B (валидирует JWT через JWKS)
         → Service C (валидирует JWT через JWKS)

  ✓ Каждый сервис независим: тестируется и деплоится изолированно
  ✓ Zero-trust по умолчанию: сервис никогда не доверяет вызывающему
    без проверки, даже внутри периметра сети
  ✗ Дублирование логики валидации (или общая библиотека — но тогда
    её версия должна синхронно обновляться во всех сервисах)
  ✗ N сервисов = N мест, где можно ошибиться в конфигурации JWKS/aud

Вариант B — API Gateway валидирует один раз, дальше доверенная сеть:

  Client → API Gateway (валидирует JWT, извлекает claims,
                         пробрасывает как internal-заголовки/
                         internal JWT с коротким TTL)
         → Service A (доверяет заголовкам ОТ GATEWAY, не проверяет
                       подпись повторно)
         → Service B (то же самое)

  ✓ Валидация в одном месте — легче поддерживать, легче обновить
    политику (например, добавить новую проверку) разом для всех
  ✓ Внутренние сервисы проще — не тянут auth-зависимости
  ✗ Gateway становится критичной точкой доверия: если его
    скомпрометировать или неправильно настроить, все сервисы
    за ним "доверяют вслепую"
  ✗ Требует чёткой сетевой изоляции ("сервис принимает трафик
    только от gateway") — иначе можно обратиться к Service A
    напрямую, минуя проверку
```

Практическая рекомендация: **вариант A (каждый сервис валидирует сам) — более безопасный дефолт**. Особенно в облачных и kubernetes-окружениях, где сетевая изоляция сама по себе не гарантирована. Соседний под в том же namespace физически может достучаться до Service A.

Вариант B оправдан, когда gateway — часть осознанной zero-trust архитектуры с mTLS (mutual TLS) между gateway и сервисами. Ради экономии одного JWKS-запроса он не оправдан: валидация JWKS дёшева, локальна и не ходит в сеть (см. статью 03), поэтому производительность — слабый аргумент.

## Client Credentials между внутренними сервисами — авторизация без пользователя

Иногда Service A вызывает Service B от своего имени, а не от имени пользователя. Это фоновая задача, cron или внутренний вызов между сервисами. Ровно для этого есть грант-тип Client Credentials из статьи 01, реализуемый конкретным NestJS-кодом.

```typescript
// service-a: получение service-to-service токена перед вызовом Service B
@Injectable()
export class ServiceTokenProvider {
  private cachedToken?: { token: string; expiresAt: number };

  constructor(private http: HttpService, private config: ConfigService) {}

  async getToken(): Promise<string> {
    if (this.cachedToken && this.cachedToken.expiresAt > Date.now()) {
      return this.cachedToken.token; // переиспользуем, пока не истёк
    }

    const response = await firstValueFrom(
      this.http.post(
        `${this.config.get('KEYCLOAK_ISSUER')}/protocol/openid-connect/token`,
        new URLSearchParams({
          grant_type: 'client_credentials',
          client_id: 'service-a',
          client_secret: this.config.get('SERVICE_A_SECRET')!,
        }),
      ),
    );

    this.cachedToken = {
      token: response.data.access_token,
      expiresAt: Date.now() + (response.data.expires_in - 30) * 1000, // запас 30с
    };
    return this.cachedToken.token;
  }
}
```

```typescript
// Использование при вызове Service B
async callServiceB() {
  const token = await this.serviceTokenProvider.getToken();
  return this.http.get('https://service-b.internal/api/data', {
    headers: { Authorization: `Bearer ${token}` },
  });
}
```

Важная деталь: **Service B валидирует этот токен тем же Guard, что и токены пользователей.** С точки зрения Resource Server разница только в содержимом payload. У токена от Client Credentials нет `sub`, указывающего на реального пользователя. Роли, если они назначены, принадлежат сервисному аккаунту `service-account-service-a`, а не человеку.

Нужно ли бизнес-логике различать "запрос от человека" и "запрос от сервиса"? Тогда проверяйте это явно — по наличию или отсутствию ожидаемых user-специфичных claims, а не отдельным Guard, дублирующим валидацию JWKS.

## "Backend должен обновлять токен" — устраняем заблуждение конкретным кодом

Уже упомянутое в статье 03 заблуждение стоит закрыть конкретной реализацией: что именно Resource Server обязан вернуть, когда токен истёк, и почему попытка самостоятельно его обновить — архитектурная ошибка.

```typescript
// Правильно: NestJS Exception Filter, отдающий структурированную 401-ошибку
@Catch(UnauthorizedException)
export class TokenExpiredFilter implements ExceptionFilter {
  catch(exception: UnauthorizedException, host: ArgumentsHost) {
    const response = host.switchToHttp().getResponse();
    response.status(401).json({
      error: 'token_expired',
      message: 'Access token is invalid or expired. Obtain a new one via refresh.',
      // Не пытаемся сходить в Keycloak и обновить токен за клиента:
      // у Resource Server нет и не должно быть refresh-токена
    });
  }
}
```

```txt
Почему backend не должен обновлять токен:

  1. У Resource Server физически нет refresh token — он лежит
     у клиента (в SPA — в памяти или httpOnly cookie, статья 06).
     Resource Server видит только access token в заголовке
     Authorization.

  2. Даже если бы backend мог получить refresh token (например,
     в BFF-архитектуре, статья 06, где это единственное законное
     исключение — но это архитектурно другая роль, не "просто API"),
     решение "когда и как повторить исходный запрос после
     обновления" принадлежит клиенту, потому что только клиент
     знает контекст исходного запроса (что повторить, с какими
     данными).

  3. Смешение ролей ломает stateless-модель Resource Server:
     если API начинает управлять токенами и решать, когда их
     обновлять, оно перестаёт быть чистым потребителем токена
     и превращается в скрытый, недокументированный auth-клиент.
```

Правильный полный цикл живёт на стороне клиента, в SPA (single-page application, одностраничное приложение). Детали для React — в статье [React SPA Integration](./05-react-spa-integration.md).

Клиент получает 401. Он пытается вызвать `updateToken()` или эквивалент через refresh token. Если получилось, он повторяет исходный запрос с новым access token. Если refresh тоже не удался (refresh token истёк или отозван), клиент инициирует полный релогин — редирект на Keycloak.

Resource Server участвует во всей этой цепочке только на первом шаге: сказать, что токен не годится. Что произойдёт дальше, он не знает.

## Итоговая связь понятий

```txt
[Ручной подход vs адаптер]      →  прозрачность и контроль против
                                  скорости разработки — зависит от
                                  требований к аудиту и вероятности
                                  смены провайдера

[Guards + декораторы]            →  аутентификация и авторизация —
                                  два последовательных, но разных
                                  Guard, не один слитный

[Authorization Services / UMA]   →  когда роли недостаточно
                                  гранулярны — ownership, контекст,
                                  политика, редактируемая без деплоя

[Монолит-валидация vs Gateway]   →  где именно живёт доверие в
                                  микросервисной архитектуре —
                                  и почему "каждый сам" безопаснее
                                  по умолчанию

[Client Credentials
 service-to-service]             →  тот же Guard, что и для
                                  пользователей — разница только
                                  в содержимом payload

[Кто обновляет токен]            →  всегда клиент; Resource Server
                                  только сообщает о невалидности
                                  через 401 + понятное тело ошибки
```

Следующая статья, [React SPA Integration](./05-react-spa-integration.md), переходит на сторону клиента. Она показывает, как React-приложение проходит Authorization Code + PKCE (Proof Key for Code Exchange). Дальше — обновление токена через `updateToken()` и что происходит, когда refresh не удаётся.

## Типичные ошибки на интервью

- **"nest-keycloak-connect — единственный правильный способ подключить Keycloak к NestJS"** — не факт. Это осознанный компромисс скорости разработки против прозрачности и независимости от вендора. Для проектов со строгими требованиями к аудиту безопасности или с реальной возможностью сменить провайдера идентификации (IdP) ручной подход на `passport-jwt` часто предпочтительнее.

- **"Guard для аутентификации и Guard для проверки ролей — можно объединить в один, так проще"** — можно, но это ухудшает переиспользуемость. Допустим, позже понадобится другой способ аутентификации, например API-ключ для сервисов, с теми же правилами авторизации. Слитный Guard придётся дублировать целиком вместо переиспользования `RolesGuard`.

- **"Authorization Services нужны всегда, простых ролей никогда не достаточно"** — избыточный ответ. Простых ролей достаточно для правил, не зависящих от конкретного экземпляра ресурса. Authorization Services оправданы, когда правило зависит от владения или контекста, или когда нетехнический сотрудник должен управлять политикой без участия разработчиков. Это архитектурное решение с реальной ценой — round-trip, когнитивная нагрузка, — а не "продвинутая практика по умолчанию".

- **"API Gateway, валидирующий токен один раз, — всегда лучше для производительности"** — JWKS-валидация локальна и дёшева (микросекунды), поэтому производительность — слабый аргумент. Вариант "каждый сервис валидирует сам" обычно безопаснее по умолчанию, особенно без строгой mTLS-изоляции между gateway и сервисами.

- **"Backend должен обновлять access token, когда видит, что тот истёк"** — нет, у Resource Server нет доступа к refresh token клиента. Единственное исключение — архитектура BFF (backend for frontend), где это отдельная, явно спроектированная роль, а не "любой backend". Правильная реакция API на истёкший токен — 401 с понятным телом ошибки; обновление токена — обязанность клиента.
