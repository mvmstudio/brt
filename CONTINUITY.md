# CONTINUITY.md

## Goal
Реализовать 5 задач из task.md: препараты (фильтр), robots.txt, избранное (JWT), деплой, граф связей.

## Constraints/Assumptions
- Mobile-first (iPhone 375px) — PWA для врачей/гомеопатов
- Lucide Icons (strokeWidth: 1.25), эмодзи в UI запрещены
- Литерата (serif) для книги, Manrope (sans) для UI
- Touch targets минимум 44x44px
- SQLite БД: remedies=542, conditions=185, nosodes=166, etiology=845, organs=490

## Key Decisions
- Алфавитный индекс (A-Z) вместо виртуализации для длинного списка
- Bottom sheet вместо модалки для авторизации
- Toggle "Только избранное" вместо отдельного таба
- Адаптивный граф: карточки на мобилке, React Flow на десктопе

## State

### Done
- [x] GitHub Issues #3-#7 созданы с тегом claude
- [x] Исследование кодовой базы завершено

### Now
- [ ] Задача 2: Поправить лимит в препаратах + фильтр + алфавитный индекс (Issue #3)

### Next
- [ ] Задача 3: robots.txt (Issue #4)
- [ ] Задача 4: Избранное + JWT (Issue #5)
- [ ] Задача 5: Деплой на brt.mvm.st (Issue #6)
- [ ] Задача 1: Граф связей (Issue #7)

## Open Questions
- Логин/пароль для BasicAuth на сервере — нужно уточнить

## Working Set
- `backend/app/api/handbook.py` — лимиты API
- `frontend/src/components/handbook/RemediesTab.tsx` — фильтр + индекс
- `frontend/src/lib/api.ts` — API клиент
- `frontend/src/app/handbook/page.tsx` — layout табов
