# Readability flags — mechanical pre-pass

Candidates only, not verdicts. Thresholds: sentence > 28 words (RU) / 25 (EN); paragraph > 6 rendered lines at 70 chars/line; > 4 prose paragraphs in a row without code/diagram/table; answer lead > 30 words or introductory opening.

Abbreviation allowlist (everything else is a candidate): API, CSS, HTML, HTTP, ID, JS, JSON, TS, URL. Brand names excluded from the CamelCase pattern: GitHub, GitLab, MacBook, MobX, MySQL, NgRx, NumPy, PayPal, PyPy, RegExp, RxJS, WiFi, YouTube.

First mentions of an abbreviation across all files: **7945**. Explained on the spot: **1371** (17.3%).

## Collections ranked by flag density

| collection | kind | files | prose words | abbrev | long sent | long para | walls | indirect leads | flags | per 1k words |
|---|---|---|---|---|---|---|---|---|---|---|
| system-design | question-bank | 2 | 13203 | 47 | 262 | 94 | 0 | 0 | 403 | 30.5 |
| web-performance | question-bank | 2 | 11144 | 55 | 188 | 91 | 0 | 0 | 334 | 30.0 |
| keycloak-auth | topic-article | 22 | 29796 | 279 | 447 | 154 | 4 | 0 | 884 | 29.7 |
| cicd-devops | question-bank | 2 | 6336 | 31 | 118 | 39 | 0 | 0 | 188 | 29.7 |
| architecture | question-bank | 2 | 13811 | 47 | 248 | 111 | 0 | 0 | 406 | 29.4 |
| aws | topic-article | 22 | 8700 | 234 | 12 | 0 | 6 | 0 | 252 | 29.0 |
| postgresql | question-bank | 2 | 9176 | 55 | 131 | 65 | 2 | 9 | 262 | 28.6 |
| solid-grasp | question-bank | 2 | 11081 | 36 | 191 | 89 | 0 | 0 | 316 | 28.5 |
| event-driven | question-bank | 2 | 13086 | 39 | 234 | 98 | 0 | 0 | 371 | 28.4 |
| canvas-graphics | topic-article | 20 | 26001 | 154 | 441 | 124 | 4 | 0 | 723 | 27.8 |
| bundlers | question-bank | 2 | 8955 | 20 | 148 | 77 | 0 | 0 | 245 | 27.4 |
| python | question-bank | 2 | 39489 | 39 | 706 | 223 | 0 | 91 | 1059 | 26.8 |
| docker | question-bank | 2 | 7177 | 35 | 115 | 41 | 0 | 0 | 191 | 26.6 |
| oop-patterns | question-bank | 2 | 16009 | 18 | 283 | 119 | 0 | 0 | 420 | 26.2 |
| security | question-bank | 2 | 11634 | 60 | 191 | 54 | 0 | 0 | 305 | 26.2 |
| tdd | question-bank | 2 | 11628 | 28 | 193 | 83 | 0 | 0 | 304 | 26.1 |
| browser-animation | topic-article | 18 | 28295 | 131 | 447 | 143 | 10 | 0 | 731 | 25.8 |
| algorithms | question-bank | 2 | 19754 | 43 | 347 | 120 | 0 | 0 | 510 | 25.8 |
| nextjs | question-bank | 2 | 43951 | 81 | 744 | 276 | 14 | 20 | 1135 | 25.8 |
| browser-runtime | question-bank | 2 | 19046 | 63 | 321 | 102 | 4 | 0 | 490 | 25.7 |
| nodejs | topic-article | 20 | 13422 | 135 | 167 | 27 | 10 | 0 | 339 | 25.3 |
| react | question-bank | 2 | 47573 | 59 | 803 | 248 | 12 | 81 | 1203 | 25.3 |
| nestjs | question-bank | 2 | 25567 | 59 | 423 | 154 | 0 | 0 | 636 | 24.9 |
| security | topic-article | 16 | 6001 | 138 | 5 | 0 | 4 | 0 | 147 | 24.5 |
| ddd | question-bank | 2 | 7900 | 18 | 129 | 43 | 2 | 0 | 192 | 24.3 |
| nodejs | question-bank | 2 | 40004 | 100 | 606 | 260 | 2 | 0 | 968 | 24.2 |
| testing | question-bank | 2 | 12731 | 30 | 216 | 61 | 0 | 0 | 307 | 24.1 |
| nextjs | topic-article | 18 | 19284 | 189 | 227 | 24 | 6 | 0 | 446 | 23.1 |
| git | question-bank | 2 | 9502 | 16 | 159 | 42 | 0 | 0 | 217 | 22.8 |
| javascript | question-bank | 2 | 56108 | 56 | 880 | 234 | 3 | 93 | 1266 | 22.6 |
| microfrontends | topic-article | 16 | 20798 | 77 | 289 | 85 | 16 | 0 | 467 | 22.5 |
| graphql | topic-article | 14 | 6010 | 70 | 52 | 6 | 3 | 0 | 131 | 21.8 |
| agile-scrum | topic-article | 16 | 31889 | 44 | 437 | 183 | 28 | 0 | 692 | 21.7 |
| css-html | question-bank | 2 | 17851 | 45 | 289 | 53 | 0 | 0 | 387 | 21.7 |
| system-design | topic-article | 24 | 22346 | 136 | 285 | 31 | 9 | 0 | 461 | 20.6 |
| python-fullstack | course-chapter | 38 | 82143 | 119 | 1241 | 251 | 52 | 0 | 1663 | 20.2 |
| postgresql | topic-article | 14 | 4924 | 55 | 38 | 0 | 3 | 0 | 96 | 19.5 |
| typescript | question-bank | 2 | 35208 | 26 | 459 | 172 | 0 | 25 | 682 | 19.4 |
| security | quiz-bank | 2 | 2559 | 26 | 13 | 10 | 0 | 0 | 49 | 19.1 |
| graphql | quiz-bank | 2 | 2794 | 6 | 20 | 27 | 0 | 0 | 53 | 19.0 |
| web-performance | quiz-bank | 2 | 1963 | 20 | 10 | 7 | 0 | 0 | 37 | 18.8 |
| cicd-devops | topic-article | 18 | 36742 | 250 | 223 | 206 | 9 | 0 | 688 | 18.7 |
| prisma | topic-article | 14 | 6041 | 51 | 23 | 31 | 4 | 0 | 109 | 18.0 |
| web-performance | topic-article | 16 | 11066 | 119 | 45 | 7 | 20 | 0 | 191 | 17.3 |
| redis | topic-article | 14 | 7050 | 61 | 22 | 30 | 8 | 0 | 121 | 17.2 |
| architecture | quiz-bank | 2 | 2049 | 15 | 7 | 13 | 0 | 0 | 35 | 17.1 |
| mongodb-mongoose | topic-article | 18 | 22104 | 80 | 218 | 58 | 14 | 0 | 370 | 16.7 |
| nextjs | quiz-bank | 2 | 3062 | 19 | 15 | 13 | 0 | 0 | 47 | 15.3 |
| solid-grasp | quiz-bank | 2 | 2486 | 19 | 4 | 13 | 0 | 0 | 36 | 14.5 |
| nx-monorepo | course-chapter | 30 | 59526 | 114 | 553 | 128 | 64 | 0 | 859 | 14.4 |
| strapi | topic-article | 14 | 4250 | 51 | 7 | 2 | 0 | 0 | 60 | 14.1 |
| react | topic-article | 22 | 27773 | 72 | 151 | 141 | 26 | 0 | 390 | 14.0 |
| build-tools | topic-article | 18 | 36031 | 105 | 263 | 103 | 26 | 0 | 497 | 13.8 |
| architecture | topic-article | 16 | 21334 | 101 | 101 | 77 | 10 | 0 | 289 | 13.5 |
| http-rest | question-bank | 2 | 2990 | 28 | 6 | 6 | 0 | 0 | 40 | 13.4 |
| angular | course-chapter | 32 | 81730 | 132 | 726 | 118 | 74 | 0 | 1050 | 12.8 |
| rabbitmq | topic-article | 14 | 15151 | 65 | 69 | 51 | 2 | 0 | 187 | 12.3 |
| nodejs | quiz-bank | 2 | 3937 | 11 | 26 | 11 | 0 | 0 | 48 | 12.2 |
| angular | question-bank | 2 | 44970 | 64 | 331 | 96 | 36 | 13 | 540 | 12.0 |
| browser-runtime | quiz-bank | 2 | 1749 | 9 | 6 | 6 | 0 | 0 | 21 | 12.0 |
| kafka | topic-article | 16 | 16497 | 59 | 59 | 54 | 22 | 0 | 194 | 11.8 |
| css-html | topic-article | 22 | 34304 | 86 | 151 | 120 | 46 | 0 | 403 | 11.7 |
| http-rest | topic-article | 18 | 16564 | 146 | 22 | 0 | 20 | 0 | 188 | 11.3 |
| oop-patterns | topic-article | 16 | 13638 | 77 | 39 | 17 | 20 | 0 | 153 | 11.2 |
| nestjs | topic-article | 20 | 5500 | 40 | 19 | 2 | 0 | 0 | 61 | 11.1 |
| state-management | topic-article | 12 | 9602 | 28 | 43 | 14 | 18 | 0 | 103 | 10.7 |
| testing | quiz-bank | 2 | 1326 | 9 | 4 | 1 | 0 | 0 | 14 | 10.6 |
| docker | quiz-bank | 2 | 1167 | 6 | 4 | 2 | 0 | 0 | 12 | 10.3 |
| prisma | question-bank | 2 | 7889 | 21 | 31 | 9 | 14 | 0 | 75 | 9.5 |
| algorithms | quiz-bank | 2 | 3156 | 10 | 13 | 7 | 0 | 0 | 30 | 9.5 |
| rxjs | topic-article | 16 | 21914 | 6 | 141 | 49 | 8 | 0 | 204 | 9.3 |
| postgresql | quiz-bank | 2 | 2781 | 14 | 10 | 2 | 0 | 0 | 26 | 9.3 |
| css-html | quiz-bank | 2 | 2711 | 8 | 11 | 5 | 0 | 0 | 24 | 8.9 |
| react | quiz-bank | 2 | 4396 | 2 | 21 | 13 | 0 | 0 | 36 | 8.2 |
| http-rest | quiz-bank | 2 | 2512 | 10 | 7 | 3 | 0 | 0 | 20 | 8.0 |
| javascript | topic-article | 26 | 23631 | 67 | 98 | 9 | 13 | 0 | 187 | 7.9 |
| typescript | topic-article | 22 | 19117 | 35 | 45 | 31 | 22 | 0 | 133 | 7.0 |
| nx | question-bank | 2 | 4136 | 8 | 19 | 0 | 2 | 0 | 29 | 7.0 |
| oop-patterns | quiz-bank | 2 | 2409 | 5 | 4 | 6 | 0 | 0 | 15 | 6.2 |
| graphql | question-bank | 2 | 3431 | 8 | 4 | 0 | 8 | 0 | 20 | 5.8 |
| nestjs | quiz-bank | 2 | 2434 | 4 | 9 | 1 | 0 | 0 | 14 | 5.8 |
| javascript | quiz-bank | 2 | 4310 | 4 | 12 | 5 | 0 | 0 | 21 | 4.9 |
| git | quiz-bank | 2 | 1945 | 2 | 6 | 1 | 0 | 0 | 9 | 4.6 |
| typescript | quiz-bank | 2 | 3676 | 4 | 4 | 8 | 0 | 0 | 16 | 4.4 |

## Worst markdown files by flag density

| file | locale | words | abbrev | long sent | % long | long para | walls | flags/1k |
|---|---|---|---|---|---|---|---|---|
| topics/aws/ru/01-aws-fundamentals.md | ru | 323 | 15 | 0 | 0.0 | 0 | 0 | 46.4 |
| topics/security/en/07-owasp-top-10.md | en | 338 | 13 | 2 | 6.1 | 0 | 0 | 44.4 |
| topics/security/ru/07-owasp-top-10.md | ru | 295 | 13 | 0 | 0.0 | 0 | 0 | 44.1 |
| topics/keycloak-auth/ru/09-keycloak-vs-alternatives.md | ru | 411 | 11 | 6 | 28.6 | 1 | 0 | 43.8 |
| topics/aws/ru/10-aws-architecture-patterns.md | ru | 281 | 11 | 1 | 3.4 | 0 | 0 | 42.7 |
| topics/aws/en/01-aws-fundamentals.md | en | 368 | 15 | 0 | 0.0 | 0 | 0 | 40.8 |
| topics/keycloak-auth/ru/08-advanced-patterns.md | ru | 795 | 15 | 13 | 40.6 | 4 | 0 | 40.3 |
| topics/keycloak-auth/en/09-keycloak-vs-alternatives.md | en | 486 | 11 | 7 | 33.3 | 1 | 0 | 39.1 |
| topics/aws/en/10-aws-architecture-patterns.md | en | 313 | 10 | 2 | 7.1 | 0 | 0 | 38.3 |
| topics/keycloak-auth/en/08-advanced-patterns.md | en | 962 | 13 | 19 | 59.4 | 4 | 0 | 37.4 |
| topics/aws/ru/09-ecs-fargate-containers.md | ru | 241 | 9 | 0 | 0.0 | 0 | 0 | 37.3 |
| topics/graphql/en/06-graphql-vs-rest.md | en | 274 | 5 | 5 | 26.3 | 0 | 0 | 36.5 |
| topics/keycloak-auth/ru/06-token-storage-and-bff-pattern.md | ru | 850 | 13 | 12 | 38.7 | 6 | 0 | 36.5 |
| topics/aws/ru/08-rds-vs-dynamodb.md | ru | 304 | 10 | 1 | 3.7 | 0 | 0 | 36.2 |
| topics/aws/en/08-rds-vs-dynamodb.md | en | 335 | 10 | 2 | 7.4 | 0 | 0 | 35.8 |
| topics/canvas-graphics/en/03-pixels-images-and-effects.md | en | 1259 | 11 | 29 | 59.2 | 5 | 0 | 35.7 |
| topics/graphql/en/02-schema-types-resolvers.md | en | 367 | 7 | 6 | 26.1 | 0 | 0 | 35.4 |
| topics/keycloak-auth/ru/10-cheatsheet-and-comparison.md | ru | 799 | 19 | 9 | 15.5 | 0 | 0 | 35.0 |
| topics/aws/ru/03-lambda-and-serverless.md | ru | 259 | 9 | 0 | 0.0 | 0 | 0 | 34.7 |
| topics/security/ru/08-security-interview-questions.md | ru | 670 | 21 | 0 | 0.0 | 0 | 2 | 34.3 |
| topics/postgresql/en/02-acid-transactions.md | en | 294 | 5 | 5 | 27.8 | 0 | 0 | 34.0 |
| topics/keycloak-auth/ru/07-security-hardening-and-attack-vectors.md | ru | 1185 | 13 | 19 | 39.6 | 8 | 0 | 33.8 |
| topics/system-design/en/02-scalability-and-load-balancing.md | en | 1185 | 14 | 24 | 42.9 | 2 | 0 | 33.8 |
| topics/nodejs/en/05-libuv-thread-pool.md | en | 449 | 6 | 8 | 30.8 | 1 | 0 | 33.4 |
| topics/canvas-graphics/ru/08-architecture-and-performance-for-canvas-apps.md | ru | 1266 | 10 | 23 | 43.4 | 9 | 0 | 33.2 |
| topics/security/en/08-security-interview-questions.md | en | 741 | 21 | 1 | 1.2 | 0 | 2 | 32.4 |
| topics/aws/ru/02-s3-and-cloudfront.md | ru | 311 | 10 | 0 | 0.0 | 0 | 0 | 32.2 |
| topics/canvas-graphics/ru/03-pixels-images-and-effects.md | ru | 1064 | 12 | 17 | 34.0 | 5 | 0 | 32.0 |
| topics/canvas-graphics/en/08-architecture-and-performance-for-canvas-apps.md | en | 1483 | 9 | 29 | 54.7 | 9 | 0 | 31.7 |
| topics/canvas-graphics/en/10-canvas-graphics-interview-questions.md | en | 2742 | 14 | 49 | 40.2 | 23 | 1 | 31.7 |
| topics/keycloak-auth/en/06-token-storage-and-bff-pattern.md | en | 1044 | 9 | 18 | 60.0 | 6 | 0 | 31.6 |
| topics/canvas-graphics/en/04-webgl-and-gpu-fundamentals.md | en | 1523 | 11 | 27 | 52.9 | 9 | 1 | 31.5 |
| topics/aws/ru/04-api-gateway.md | ru | 259 | 8 | 0 | 0.0 | 0 | 0 | 30.9 |
| topics/keycloak-auth/en/07-security-hardening-and-attack-vectors.md | en | 1422 | 12 | 24 | 50.0 | 8 | 0 | 30.9 |
| topics/keycloak-auth/en/11-keycloak-auth-interview-questions.md | en | 3150 | 24 | 46 | 30.5 | 25 | 2 | 30.8 |
| topics/aws/en/05-iam-security.md | en | 293 | 7 | 2 | 8.0 | 0 | 0 | 30.7 |
| topics/browser-animation/en/06-performance-debugging-and-jank-hunting.md | en | 1598 | 12 | 28 | 44.4 | 7 | 2 | 30.7 |
| topics/canvas-graphics/ru/04-webgl-and-gpu-fundamentals.md | ru | 1304 | 11 | 18 | 34.0 | 10 | 1 | 30.7 |
| topics/browser-animation/ru/06-performance-debugging-and-jank-hunting.md | ru | 1308 | 13 | 19 | 30.2 | 6 | 2 | 30.6 |
| topics/aws/en/02-s3-and-cloudfront.md | en | 361 | 9 | 2 | 6.2 | 0 | 0 | 30.5 |

## Question / quiz banks

| file | locale | words | abbrev | long sent | % long | long para | walls | indirect leads | indirect lead pct | flags/1k |
|---|---|---|---|---|---|---|---|---|---|---|
| questions/system-design.json#ru | ru | 6251 | 23 | 124 | 68.1 | 48 | 0 | 0 | 0.0 | 31.2 |
| questions/web-performance.json#ru | ru | 5315 | 28 | 88 | 53.3 | 49 | 0 | 0 | 0.0 | 31.0 |
| questions/architecture.json#en | en | 7335 | 23 | 143 | 63.8 | 55 | 0 | 0 | 0.0 | 30.1 |
| questions/cicd-devops.json#en | en | 3328 | 15 | 68 | 61.8 | 17 | 0 | 0 | 0.0 | 30.0 |
| questions/system-design.json#en | en | 6952 | 24 | 138 | 75.8 | 46 | 0 | 0 | 0.0 | 29.9 |
| questions/postgresql.json#en | en | 4892 | 27 | 80 | 40.8 | 31 | 1 | 5 | 20.0 | 29.4 |
| questions/cicd-devops.json#ru | ru | 3008 | 16 | 50 | 45.0 | 22 | 0 | 0 | 0.0 | 29.3 |
| questions/solid-grasp.json#en | en | 5826 | 18 | 111 | 57.8 | 40 | 0 | 0 | 0.0 | 29.0 |
| questions/web-performance.json#en | en | 5829 | 27 | 100 | 60.6 | 42 | 0 | 0 | 0.0 | 29.0 |
| questions/event-driven.json#ru | ru | 6190 | 19 | 107 | 62.6 | 52 | 0 | 0 | 0.0 | 28.8 |
| questions/architecture.json#ru | ru | 6476 | 24 | 105 | 45.5 | 56 | 0 | 0 | 0.0 | 28.6 |
| questions/event-driven.json#en | en | 6896 | 20 | 127 | 73.8 | 46 | 0 | 0 | 0.0 | 28.0 |
| questions/solid-grasp.json#ru | ru | 5255 | 18 | 80 | 39.0 | 49 | 0 | 0 | 0.0 | 28.0 |
| questions/bundlers.json#en | en | 4687 | 10 | 83 | 53.9 | 38 | 0 | 0 | 0.0 | 27.9 |
| questions/postgresql.json#ru | ru | 4284 | 28 | 51 | 26.0 | 34 | 1 | 4 | 16.0 | 27.5 |
| questions/browser-runtime.json#en | en | 9944 | 31 | 190 | 52.8 | 48 | 2 | 0 | 0.0 | 27.3 |
| questions/oop-patterns.json#en | en | 8486 | 8 | 165 | 61.3 | 59 | 0 | 0 | 0.0 | 27.3 |
| questions/tdd.json#en | en | 6187 | 14 | 115 | 51.3 | 40 | 0 | 0 | 0.0 | 27.3 |
| questions/security.json#en | en | 6168 | 29 | 115 | 53.2 | 24 | 0 | 0 | 0.0 | 27.2 |
| questions/docker.json#en | en | 3798 | 17 | 66 | 48.2 | 20 | 0 | 0 | 0.0 | 27.1 |
| questions/python.json#en | en | 20725 | 19 | 393 | 71.1 | 99 | 0 | 49 | 50.0 | 27.0 |
| questions/react.json#en | en | 27649 | 30 | 511 | 57.7 | 144 | 6 | 50 | 51.0 | 26.8 |
| questions/bundlers.json#ru | ru | 4268 | 10 | 65 | 41.1 | 39 | 0 | 0 | 0.0 | 26.7 |
| questions/python.json#ru | ru | 18764 | 20 | 313 | 56.3 | 124 | 0 | 42 | 42.9 | 26.6 |
| questions/algorithms.json#en | en | 10372 | 22 | 195 | 57.0 | 57 | 0 | 0 | 0.0 | 26.4 |
| questions/ddd.json#en | en | 4200 | 9 | 80 | 49.4 | 21 | 1 | 0 | 0.0 | 26.4 |
| questions/nextjs.json#en | en | 23284 | 40 | 423 | 54.4 | 131 | 7 | 10 | 14.3 | 26.2 |
| questions/docker.json#ru | ru | 3379 | 18 | 49 | 35.3 | 21 | 0 | 0 | 0.0 | 26.0 |
| questions/nodejs.json#en | en | 21262 | 49 | 366 | 45.2 | 132 | 1 | 0 | 0.0 | 25.8 |
| questions/nextjs.json#ru | ru | 20667 | 41 | 321 | 40.8 | 145 | 7 | 10 | 14.3 | 25.4 |
| questions/algorithms.json#ru | ru | 9382 | 21 | 152 | 43.9 | 63 | 0 | 0 | 0.0 | 25.2 |
| questions/nestjs.json#en | en | 13477 | 28 | 238 | 49.8 | 73 | 0 | 0 | 0.0 | 25.2 |
| questions/security.json#ru | ru | 5466 | 31 | 76 | 34.1 | 30 | 0 | 0 | 0.0 | 25.1 |
| questions/oop-patterns.json#ru | ru | 7523 | 10 | 118 | 42.9 | 60 | 0 | 0 | 0.0 | 25.0 |
| questions/javascript.json#en | en | 35085 | 29 | 621 | 58.8 | 164 | 2 | 58 | 45.0 | 24.9 |
| questions/tdd.json#ru | ru | 5441 | 14 | 78 | 34.5 | 43 | 0 | 0 | 0.0 | 24.8 |
| questions/testing.json#en | en | 6705 | 15 | 124 | 56.1 | 27 | 0 | 0 | 0.0 | 24.8 |
| questions/nestjs.json#ru | ru | 12090 | 31 | 185 | 38.1 | 81 | 0 | 0 | 0.0 | 24.6 |
| questions/browser-runtime.json#ru | ru | 9102 | 32 | 131 | 36.2 | 54 | 2 | 0 | 0.0 | 24.1 |
| questions/testing.json#ru | ru | 6026 | 15 | 92 | 41.4 | 34 | 0 | 0 | 0.0 | 23.4 |

## RU vs EN — is the English version harder?

| file | RU % long sent | EN % long sent | EN − RU | RU abbrev | EN abbrev |
|---|---|---|---|---|---|
| nodejs/*/05-libuv-thread-pool.md | 3.8 | 30.8 | 27.0 | 6 | 6 |
| nextjs/*/06-routing-layouts-middleware.md | 6.1 | 31.9 | 25.8 | 7 | 7 |
| canvas-graphics/*/03-pixels-images-and-effects.md | 34.0 | 59.2 | 25.2 | 12 | 11 |
| canvas-graphics/*/07-svg-d3-and-choosing-a-viz-technology.md | 34.3 | 58.3 | 24.0 | 4 | 3 |
| system-design/*/02-scalability-and-load-balancing.md | 20.0 | 42.9 | 22.9 | 13 | 14 |
| postgresql/*/02-acid-transactions.md | 5.6 | 27.8 | 22.2 | 4 | 5 |
| course:nx-monorepo/*/13-ci-and-nx-cloud.md | 10.3 | 32.2 | 21.9 | 6 | 8 |
| course:python-fullstack/*/11-concurrency-fundamentals.md | 29.2 | 51.1 | 21.9 | 8 | 6 |
| graphql/*/02-schema-types-resolvers.md | 4.3 | 26.1 | 21.8 | 4 | 7 |
| browser-animation/*/07-motion-design-patterns-and-accessibility.md | 24.1 | 45.8 | 21.7 | 6 | 4 |
| keycloak-auth/*/06-token-storage-and-bff-pattern.md | 38.7 | 60.0 | 21.3 | 13 | 9 |
| graphql/*/06-graphql-vs-rest.md | 5.3 | 26.3 | 21.0 | 5 | 5 |
| system-design/*/03-caching.md | 11.6 | 32.6 | 21.0 | 5 | 4 |
| agile-scrum/*/08-agile-scrum-interview-questions.md | 19.3 | 39.7 | 20.4 | 8 | 7 |
| nodejs/*/04-microtasks-macrotasks-nexttick.md | 28.0 | 48.0 | 20.0 | 1 | 1 |
| canvas-graphics/*/10-canvas-graphics-interview-questions.md | 20.7 | 40.2 | 19.5 | 14 | 14 |
| microfrontends/*/01-microfrontends-fundamentals.md | 10.8 | 30.2 | 19.4 | 6 | 5 |
| course:python-fullstack/*/04-oop-and-dataclasses.md | 26.1 | 45.2 | 19.1 | 3 | 3 |
| graphql/*/05-performance-security.md | 4.8 | 23.8 | 19.0 | 2 | 5 |
| canvas-graphics/*/04-webgl-and-gpu-fundamentals.md | 34.0 | 52.9 | 18.9 | 11 | 11 |
| keycloak-auth/*/08-advanced-patterns.md | 40.6 | 59.4 | 18.8 | 15 | 13 |
| keycloak-auth/*/04-nestjs-resource-server.md | 28.3 | 46.7 | 18.4 | 11 | 10 |
| system-design/*/11-system-design-interview-framework.md | 16.0 | 34.3 | 18.3 | 8 | 5 |
| course:angular/*/07-routing.md | 4.7 | 23.0 | 18.3 | 1 | 1 |
| canvas-graphics/*/06-threejs-in-depth.md | 29.1 | 47.3 | 18.2 | 7 | 8 |
| postgresql/*/04-indexes-internals.md | 4.5 | 22.7 | 18.2 | 2 | 1 |
| system-design/*/07-websockets-and-realtime.md | 15.9 | 34.1 | 18.2 | 5 | 5 |
| graphql/*/01-graphql-fundamentals.md | 16.7 | 34.8 | 18.1 | 6 | 4 |
| system-design/*/10-notification-system.md | 14.3 | 32.4 | 18.1 | 4 | 4 |
| microfrontends/*/05-routing-and-navigation.md | 20.5 | 38.5 | 18.0 | 2 | 1 |

## Most frequent unexpanded abbreviations across all files

| abbreviation | kind | files where first use is unexplained |
|---|---|---|
| DOM | upper | 157 |
| UI | upper | 152 |
| CI | upper | 109 |
| CPU | upper | 106 |
| SQL | upper | 90 |
| БД | cyrillic | 88 |
| CDN | upper | 87 |
| DB | upper | 78 |
| REST | upper | 69 |
| CLI | upper | 65 |
| AWS | upper | 64 |
| TTL | upper | 64 |
| SSR | upper | 63 |
| JWT | upper | 58 |
| DI | upper | 56 |
| JSX | upper | 54 |
| CRUD | upper | 52 |
| UX | upper | 52 |
| GPU | upper | 49 |
| SPA | upper | 48 |
| ORM | upper | 45 |
| TCP | upper | 45 |
| CORS | upper | 44 |
| PR | upper | 43 |
| OS | upper | 42 |
| XSS | upper | 40 |
| V8 | upper | 39 |
| CD | upper | 37 |
| S3 | upper | 37 |
| SEO | upper | 37 |
| ESM | upper | 37 |
| DNS | upper | 36 |
| GC | upper | 35 |
| SDK | upper | 33 |
| HTTPS | upper | 31 |
| SVG | upper | 31 |
| ES | upper | 31 |
| IP | upper | 29 |
| ОС | cyrillic | 27 |
| e2e | numeronym | 27 |
| TLS | upper | 27 |
| SHA | upper | 25 |
| SLA | upper | 24 |
| SQS | upper | 24 |
| BFF | upper | 24 |
| RAM | upper | 23 |
| LCP | upper | 23 |
| CJS | upper | 23 |
| RSC | upper | 22 |
| CSRF | upper | 22 |
| RPC | upper | 22 |
| SSG | upper | 22 |
| CLS | upper | 20 |
| ACID | upper | 19 |
| ECS | upper | 18 |
| HMAC | upper | 18 |
| HMR | upper | 18 |
| AST | upper | 18 |
| OOP | upper | 18 |
| FIFO | upper | 17 |
