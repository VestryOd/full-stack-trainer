<!-- verified: 2026-06-05, corrections: 0 -->
# Dynamic Modules

## Очень популярный Senior вопрос

Обычный Module:

```ts
@Module({
 providers: [...]
})
```

---

Статический.

---

Конфигурация известна заранее.

---

Но что делать если:

```txt
нужна конфигурация
из environment
из runtime
из внешнего API
```

---

Решение:

```txt
Dynamic Module
```

---

# Что такое Dynamic Module

Модуль,
который может генерировать
свою конфигурацию динамически.

---

# Самый известный пример

```ts
ConfigModule.forRoot()
```

---

Ты наверняка использовал.

---

```ts
ConfigModule.forRoot({
 isGlobal: true
})
```

---

Это Dynamic Module.

---

# Почему

Потому что:

```txt
@Module(...)
```

генерируется во время выполнения.

---

# Структура

```ts
static forRoot()
: DynamicModule
```

---

Пример.

---

```ts
@Module({})
export class DatabaseModule {

 static forRoot(
  options
 ): DynamicModule {

  return {

   module:
    DatabaseModule,

   providers: [...]
  };
 }
}
```

---

# Использование

```ts
DatabaseModule.forRoot({
 host: 'localhost'
})
```

---

# Что возвращает

Очень важно.

---

DynamicModule:

```ts
{
 module,
 providers,
 exports,
 imports
}
```

---

Фактически:

```txt
динамически создаем @Module
```

---

# Зачем это нужно

Позволяет:

```txt
передавать настройки
при подключении модуля
```

---

# Реальный пример

```ts
JwtModule.register({
 secret: '123'
})
```

---

Это Dynamic Module.

---

# register()

Очень распространенный паттерн.

---

```ts
Module.register()
```

---

Используется когда:

```txt
конфиг известен сразу
```

---

# registerAsync()

Еще популярнее.

---

```ts
JwtModule.registerAsync(...)
```

---

Используется когда:

```txt
нужно ждать зависимости
```

---

Например:

```txt
ConfigService
Vault
AWS Secrets
```

---

# Пример

```ts
JwtModule.registerAsync({

 inject: [ConfigService],

 useFactory: (config) => ({

  secret:
   config.get('JWT_SECRET')

 })
})
```

---

# Почему registerAsync важен

Во время старта:

```txt
ConfigService уже создан
```

---

И можем использовать его.

---

# Global Dynamic Module

Очень популярный вопрос.

---

Можно сделать:

```ts
@Global()
```

---

Тогда:

```txt
не нужно импортировать
в каждом модуле
```

---

# forFeature()

Еще один популярный паттерн.

---

Например:

```ts
TypeOrmModule.forFeature(...)
```

---

Используется для:

```txt
локальной регистрации
repository
entity
feature providers
```

---

# Разница

forRoot:

```txt
один раз
на всё приложение
```

---

forFeature:

```txt
для конкретного модуля
```

---

# Частый вопрос

Почему Dynamic Module лучше обычного Module?

---

Ответ:

Позволяет передавать конфигурацию во время подключения и создавать провайдеры динамически.

---

# Частый вопрос

Какие встроенные Dynamic Modules знаете?

---

Например:

```txt
ConfigModule.forRoot()
JwtModule.register()
TypeOrmModule.forRoot()
GraphQLModule.forRoot()
```

---

# Частый вопрос

Когда использовать registerAsync?

---

Когда конфигурация зависит от других провайдеров.

---

Например:

```txt
ConfigService
Secrets Manager
Vault
```

---

# Interview Answer

Dynamic Module — это модуль, который создается динамически во время выполнения и может принимать конфигурацию через методы вроде forRoot, register или registerAsync. Этот механизм активно используется во встроенных модулях NestJS, таких как ConfigModule, JwtModule и GraphQLModule.