# Second Brain Dashboard

## Recent additions
```dataview
TABLE date, type, status
FROM "wiki"
SORT date DESC
LIMIT 10
```

## Needs attention (seedlings)
```dataview
LIST
FROM "wiki"
WHERE status = "seedling"
SORT file.mtime ASC
LIMIT 10
```

## Unprocessed inbox
```dataview
LIST
FROM "raw"
WHERE file.folder = "raw"
SORT file.ctime ASC
```

## Orphan notes
```dataview
LIST
FROM "wiki"
WHERE length(file.outlinks) = 0
```
