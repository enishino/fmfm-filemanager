create table "books" (
	"number"	INTEGER UNIQUE,
	"title"	TEXT,
	"tags"	TEXT,
    "r2l" INTEGER,
    "spread" INTEGER,
	"md5"	TEXT,
    "filetype" TEXT,
    "pagenum" REAL,
	"hide"	INTEGER,
	"state_num"	INTEGER,
	"document_date"	TEXT,
	"registered_date"	TEXT,
	"modified_date"	TEXT
);
create virtual table fts using fts5(number, page, ngram);
