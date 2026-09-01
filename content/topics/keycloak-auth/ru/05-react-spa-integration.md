# React SPA — интеграция с Keycloak

## От протокола к реальному React-приложению

Эта статья смотрит на Keycloak с другой стороны провода. React-приложение должно инициировать логин, пережить обновление страницы, обновлять токен без раздражения пользователя и корректно обработать логаут.

Статьи 01-04 дали протокольный фундамент и то, как выглядит правильный backend. Большинство практических ошибок реальных проектов совершается именно здесь. Не потому что React сложен. Тонкости браузерных механизмов — iframe, cookie-политики — плохо документированы и почти никогда не всплывают на локальной разработке.

## Почему Authorization Code + PKCE — единственный вариант для SPA

React SPA (single-page application, одностраничное приложение) — это **public client** по определению из статьи 02. Весь код исполняется в браузере пользователя, значит, любой "секрет", зашитый в JS-бандл, доступен любому, кто откроет DevTools → Sources.

Единственный протокольно корректный флоу для такого клиента — Authorization Code + PKCE (Proof Key for Code Exchange), полная последовательность разобрана в статье 01. Здесь `client_secret` не требуется вообще, а `code_verifier` защищает от перехвата authorization code без всякого секрета.

Implicit Grant исторически использовался именно для таких приложений. Статья 01 объясняет, почему он отброшен: токен едет через URL fragment — открытым текстом, в историю браузера. Сегодня ни один современный адаптер не предлагает Implicit по умолчанию, включая `keycloak-js`.

## keycloak-js — основной адаптер, шаг за шагом

`keycloak-js` — официальная JS-библиотека Keycloak, реализующая Authorization Code + PKCE флоу и управление токенами для браузерных приложений.

```typescript
// keycloak.ts — единственный экземпляр на всё приложение
import Keycloak from 'keycloak-js';

export const keycloak = new Keycloak({
  url: 'https://keycloak.example.com',
  realm: 'myrealm',
  clientId: 'spa-client', // public client, без secret
});
```

```typescript
// App.tsx — инициализация при старте приложения
async function initAuth() {
  const authenticated = await keycloak.init({
    onLoad: 'check-sso', // см. разбор ниже
    silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
    pkceMethod: 'S256', // явно включить PKCE (в новых версиях — дефолт)
  });
  return authenticated;
}
```

### `onLoad: 'check-sso'` vs `'login-required'`

Это первое решение, которое приходится принять, и оно определяет всё удобство работы с приложением:

```txt
onLoad: 'login-required':
  При заходе на любую страницу приложения, если пользователь не
  аутентифицирован — немедленный редирект на Keycloak login.
  Подходит: приложения, где 100% функциональности требует логина
  (внутренние админки, дашборды) — "анонимного" состояния нет.

onLoad: 'check-sso':
  При заходе на страницу — тихая, невидимая проверка "может, у
  пользователя уже есть активная SSO-сессия в Keycloak (залогинен
  в другом табе/приложении)?" без редиректа, если сессии нет —
  приложение остаётся в неаутентифицированном состоянии, доступном
  визуально (можно показать landing page, кнопку "Войти").
  Подходит: приложения со смешанным контентом — есть публичные
  страницы (лендинг, документация) и страницы, требующие логина.
```

Механизм `check-sso` — это именно то место, где скрывается самая известная практическая проблема этой темы, разбираемая ниже.

## silent-check-sso — как это работает и почему это хрупко в реальности

Чтобы проверить "есть ли активная сессия в Keycloak" без видимого редиректа пользователя на чужой домен, `keycloak-js` использует классический трюк. Он создаёт **невидимый `<iframe>`**, который грузит специальную страницу с домена Keycloak. Та, в свою очередь, "рассказывает" родительскому окну о результате через `postMessage`.

```txt
1. React-приложение (https://app.example.com) при старте создаёт
   невидимый iframe с src = https://keycloak.example.com/...
   &prompt=none

2. Если у пользователя есть активная сессия на домене
   keycloak.example.com (Keycloak поставил свою cookie сессии
   при предыдущем логине), Keycloak внутри iframe сразу отдаёт
   authorization code, без формы логина

3. iframe редиректится на silent-check-sso.html (тоже на домене
   app.example.com — файл из статического хостинга приложения),
   который через postMessage передаёт code родительскому окну

4. Родительское окно обменивает code на токены (back-channel,
   см. статью 01) — пользователь никогда не видел ни формы логина,
   ни самого iframe
```

```html
<!-- public/silent-check-sso.html — минимальная статическая страница -->
<!DOCTYPE html>
<html>
  <body>
    <script>
      parent.postMessage(location.href, location.origin);
    </script>
  </body>
</html>
```

Проблема в шаге 2. Keycloak должен "узнать" пользователя внутри iframe, без формы логина. Для этого браузер должен отправить cookie сессии Keycloak **внутри iframe, встроенного в чужой домен**. Чужой — это с точки зрения Keycloak: app.example.com.

С точки зрения браузера это классический сценарий **third-party cookie**. Cookie принадлежит домену keycloak.example.com, а отправляется, пока пользователь физически находится на app.example.com.

```txt
Safari ITP (Intelligent Tracking Prevention):
  Блокирует third-party cookies по умолчанию уже много лет.
  silent-check-sso просто не работает в Safari "из коробки":
  iframe грузится, но cookie сессии Keycloak не отправляется,
  Keycloak внутри iframe не видит пользователя как залогиненного —
  даже если у него открыта активная сессия в соседней вкладке.

Chrome, поэтапный отказ от third-party cookies:
  Тот же итоговый эффект, поэтапно раскатываемый по всем браузерам
  на движке Chromium — third-party cookies перестают быть надёжным
  механизмом кросс-доменной идентификации в принципе.

Итоговый практический эффект:
  Пользователь может быть реально залогинен в Keycloak: сессия
  жива, он только что логинился в соседней вкладке того же
  приложения или в другом клиенте того же realm. Но silent-check-sso
  молча "не находит" сессию, приложение считает пользователя
  неаутентифицированным, и он видит экран логина, хотя формально
  уже вошёл в систему.
  Это выглядит как "приложение то и дело внезапно разлогинивает",
  хотя на самом деле проблема — в механизме проверки, а не в logout.
```

Это не гипотетическая, а систематическая production-проблема. Обсуждения "почему `keycloak-js` check-sso не работает в Safari" встречаются в issue-трекерах повсеместно. Дело не в баге библиотеки, а в фундаментальном конфликте между iframe-based silent-check и современной политикой браузеров против третьесторонних cookie.

```txt
Практические митигации (ни одна не убирает проблему полностью):

  1. Принять как факт: "check-sso может ошибочно показать
     неаутентифицированное состояние в Safari". И убедиться, что
     на этот случай всё выглядит нормально: кнопка "Войти" видна
     и работает, а не белый экран

  2. Использовать 'login-required' вместо 'check-sso', если у
     приложения нет реального анонимного контента — тогда проблема
     silent-check-sso не встаёт вообще, потому что редирект явный

  3. Переходить на BFF-паттерн (статья 06) — там идентификация
     сессии идёт через first-party cookie самого приложения,
     а не через cross-domain iframe-трюк, и проблема third-party
     cookie исчезает архитектурно, а не патчами
```

## Логин, логаут, обновление токена — базовое API

```typescript
// Инициировать логин — редирект на Keycloak (полноценный, не в iframe)
function login() {
  keycloak.login({ redirectUri: window.location.origin + '/dashboard' });
}

// Логаут — редирект на Keycloak logout endpoint (front-channel, см. статью 03)
function logout() {
  keycloak.logout({ redirectUri: window.location.origin });
}

// updateToken — обновление access token через refresh token
// minValidity: обновить, ЕСЛИ токен истечёт менее чем через N секунд
async function ensureFreshToken(): Promise<string> {
  try {
    const refreshed = await keycloak.updateToken(30);
    if (refreshed) {
      console.debug('Token was refreshed');
    }
    return keycloak.token!;
  } catch {
    // refresh token тоже недействителен/истёк — единственный
    // корректный выход - полный релогин, см. раздел про React Query ниже
    keycloak.login();
    throw new Error('Session expired, redirecting to login');
  }
}
```

Важная деталь про `updateToken(minValidity)`. Если вызвать его, когда токен и так свежий — осталось больше `minValidity` секунд, — `keycloak-js` **не делает сетевой запрос вообще**. Он просто возвращает `false`, то есть "обновление не потребовалось". Поэтому метод безопасно вызывать перед каждым запросом к API, не рискуя "зафлудить" Keycloak.

## Альтернатива: `oidc-client-ts` / `react-oidc-context` — портируемость вместо keycloak-специфики

`keycloak-js` удобен и хорошо документирован именно для Keycloak. Но он содержит keycloak-специфичные детали API (`updateToken`, формат `onLoad`), которые не переносятся напрямую на другого провайдера OIDC (OpenID Connect). Альтернатива — **`oidc-client-ts`** и React-обёртка `react-oidc-context`. Эта библиотека реализует OIDC как стандарт протокола, без привязки к вендору.

```tsx
// Пример на react-oidc-context — конфиг говорит на языке протокола,
// а не Keycloak-специфичных терминов
import { AuthProvider } from 'react-oidc-context';

const oidcConfig = {
  authority: 'https://keycloak.example.com/realms/myrealm', // сработает и для Auth0/Okta
  client_id: 'spa-client',
  redirect_uri: window.location.origin + '/callback',
  scope: 'openid profile email',
  automaticSilentRenew: true, // тот же silent-iframe механизм, те же ограничения ITP
};

function App() {
  return (
    <AuthProvider {...oidcConfig}>
      <Dashboard />
    </AuthProvider>
  );
}
```

```txt
Когда выбирать keycloak-js:
  - Проект точно и надолго привязан к Keycloak
  - Нужны keycloak-специфичные фичи (Authorization Services из
    статьи 04 имеют собственный JS-хелпер в экосистеме Keycloak)
  - Команда уже знакома с Keycloak-терминологией адаптера

Когда выбирать oidc-client-ts/react-oidc-context:
  - Важна теоретическая независимость от вендора (миграция на
    Auth0/Okta/Cognito не должна требовать переписывания auth-слоя
    приложения — см. сравнение в статье 09)
  - Команда предпочитает работать в терминах протокола (OIDC),
    а не терминах конкретного продукта
  - Мультипровайдерная стратегия (разные клиенты на разных IdP)

Важная оговорка: silent-check-sso и silent renew в обеих
библиотеках используют один и тот же механизм iframe +
third-party cookie. Переход на oidc-client-ts сам по себе
не решает проблему Safari ITP, он лишь меняет API, которым вы
обёрнуты. Настоящее решение этой хрупкости — архитектурное
(BFF, статья 06), а не смена библиотеки.
```

## Токены в fetch/axios/React Query — правильная сборка

Токену нужны четыре вещи:

- Прикрепляться к каждому запросу.
- Обновляться, когда API отвечает `401`.
- Повторять исходный запрос после обновления.
- Корректно сдаваться — форс-релогин, — если обновление не удалось.

```typescript
// axios-интерцептор — прикрепление токена + retry после обновления
import axios from 'axios';
import { keycloak } from './keycloak';

const api = axios.create({ baseURL: '/api' });

api.interceptors.request.use(async (config) => {
  await keycloak.updateToken(30); // не делает запрос, если токен ещё свежий
  config.headers.Authorization = `Bearer ${keycloak.token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true; // защита от бесконечного цикла retry
      try {
        await keycloak.updateToken(-1); // форсированное обновление
        originalRequest.headers.Authorization = `Bearer ${keycloak.token}`;
        return api(originalRequest); // повторяем ИСХОДНЫЙ запрос с новым токеном
      } catch {
        keycloak.login(); // refresh тоже не удался — полный релогин
      }
    }
    return Promise.reject(error);
  },
);
```

```typescript
// React Query — глобальная обработка 401 без ручного оборачивания каждого useQuery
import { QueryClient, QueryCache } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      if (isAxios401(error)) {
        // axios-интерцептор выше уже попытался обновить токен и повторить —
        // если ошибка всё равно долетела сюда, значит, форс-релогин
        // уже инициирован интерцептором; здесь достаточно просто
        // не показывать пользователю "сырую" 401-ошибку в UI
      }
    },
  }),
});
```

Ключевой архитектурный момент: **логика "обновить токен → повторить запрос → сдаться и разлогинить" живёт в одном месте, в интерцепторе.** Она не размазана по каждому вызову API. Именно так клиентская сторона выполняет обязательство из статьи 04: backend не обновляет токен, это работа клиента.

## Защищённые роуты и корректный цикл логаута

```tsx
// ProtectedRoute — обёртка для роутов, требующих аутентификации
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { keycloak, initialized } = useKeycloak();

  if (!initialized) return <LoadingSpinner />; // ещё идёт check-sso
  if (!keycloak.authenticated) {
    keycloak.login({ redirectUri: window.location.href }); // вернуться СЮДА после логина
    return <LoadingSpinner />;
  }
  return <>{children}</>;
}
```

Частая ошибка при логауте — забыть, что `keycloak.logout()` делает **полный редирект браузера** (front-channel, статья 03), а не просто чистит локальное состояние. Без `redirectUri` пользователь может застрять на дефолтной странице Keycloak вместо возврата в приложение.

Второй частый баг — порядок очистки. Допустим, приложение чистит локальное React-состояние (React Query cache, Redux store) до вызова `keycloak.logout()`. Лишние ре-рендеры в этот момент уже не важны: браузер всё равно уходит на другой домен.

Опасность в другом. Пусть логика логаута ждёт, пока асинхронная очистка кэша завершится. Если редирект уводит браузер раньше, чем промис резолвится, часть очистки не выполнится. Обычная жертва — отправка аналитики о логауте.

```typescript
// Правильный порядок — cleanup синхронно/быстро, ПОТОМ редирект
function handleLogout() {
  queryClient.clear(); // синхронная очистка кэша React Query
  analytics.track('logout'); // fire-and-forget, не блокирует
  keycloak.logout({ redirectUri: window.location.origin }); // редирект — последний шаг
}
```

## Итоговая связь понятий

```txt
[Auth Code + PKCE для SPA]      →  единственный корректный флоу для
                                  public client — прямое следствие
                                  протокольных ограничений статьи 01

[onLoad: check-sso vs
 login-required]                 →  выбор зависит от того, есть ли
                                  у приложения анонимный контент

[silent-check-sso + iframe]      →  элегантный механизм, который
                                  разбивается о third-party cookie
                                  ограничения Safari и Chrome —
                                  проблема системная, не случайная

[keycloak-js vs oidc-client-ts]  →  удобство vs портируемость; обе
                                  используют один и тот же хрупкий
                                  iframe-механизм под капотом

[axios/React Query интеграция]   →  логика refresh-retry-relogin
                                  живёт в одном месте, в
                                  интерцепторе, а не по вызовам

[Logout redirect cycle]          →  logout — это редирект, а не
                                  просто очистка состояния; порядок
                                  cleanup vs редирект имеет значение
```

Следующая статья — [Token Storage and the BFF Pattern](./06-token-storage-and-bff-pattern.md), где BFF расшифровывается как backend for frontend. Она берёт именно проблему из этой статьи: хрупкость silent-check-sso и необходимость доверять браузерному хранилищу токенов. Решает она эту проблему сменой модели, а не патчами.

## Типичные ошибки на интервью

- **"Implicit Grant проще для SPA, значит его стоит использовать, если PKCE кажется сложным"** — нет. Implicit признан небезопасным паттерном (см. статью 01). А PKCE полностью инкапсулирован внутри `keycloak-js` и `oidc-client-ts`, так что его "сложность" вообще не проявляется в прикладном коде. Это не повод возвращаться к устаревшему флоу.

- **"check-sso всегда надёжно определяет, залогинен ли пользователь"** — нет. Он систематически ломается в Safari, где ITP (Intelligent Tracking Prevention) блокирует third-party cookies, и постепенно ломается в Chrome. Приложение может ошибочно посчитать реально залогиненного пользователя неаутентифицированным. Хороший ответ упоминает эту хрупкость и знает хотя бы одну митигацию: `login-required` вместо `check-sso` или паттерн BFF.

- **"`oidc-client-ts` решает проблему silent-check-sso, потому что это более современная библиотека"** — нет. Обе библиотеки используют один и тот же механизм iframe + third-party cookie под капотом. Смена библиотеки не убирает фундаментальное ограничение браузерных cookie-политик, она только меняет API.

- **"Токен можно просто хранить в переменной и прикреплять к запросам, refresh обработаем отдельно, если понадобится"** — недооценка. Без централизованной retry-логики в интерцепторе каждый вызов API должен сам обрабатывать истечение токена. Это почти гарантированно приводит к дублированию кода и пропущенным случаям: забыли обработать 401 в одном из полусотни мест вызова.

- **"Logout — просто вызвать `keycloak.logout()`, больше ничего думать не нужно"** — упускает две вещи. Первая: `redirectUri` обязателен, иначе пользователь застревает на странице Keycloak. Вторая: важен порядок очистки — если приложение полагается на асинхронную очистку состояния до редиректа, синхронный уход браузера может её прервать.
