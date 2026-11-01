import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../static/_core/scripts/content-enhancements.js', import.meta.url), 'utf8');
const { tableToTsv } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const cell = (innerText, colSpan = 1, rowSpan = 1) => ({ innerText, colSpan, rowSpan });
const table = cells => {
  const rows = cells.map((cells, sectionRowIndex) => ({ cells, sectionRowIndex }));
  rows.forEach(row => { row.parentElement = { rows }; });
  return { rows };
};

test('copies headers and Japanese text as spreadsheet rows and columns', () => {
  assert.equal(tableToTsv(table([
    [cell('曜日'), cell('午前'), cell('午後')],
    [cell('月'), cell('おはよう'), cell('こんにちは')],
  ])), '曜日\t午前\t午後\n月\tおはよう\tこんにちは');
});

test('quotes tabs and newlines and escapes quotes inside quoted fields', () => {
  assert.equal(tableToTsv(table([
    [cell('  first\nsecond  '), cell('a\tb'), cell('say "hello"')],
  ])), '"first\nsecond"\t"a\tb"\t"say ""hello"""');
});

test('keeps columns aligned across row and column spans', () => {
  assert.equal(tableToTsv(table([
    [cell('Monday', 1, 2), cell('Morning'), cell('Night')],
    [cell('Any time', 2)],
    [cell('Tuesday'), cell('Hello'), cell('Good night')],
  ])), 'Monday\tMorning\tNight\n\tAny time\t\nTuesday\tHello\tGood night');
});

test('handles a row span through the end of its row group and empty tables', () => {
  assert.equal(tableToTsv(table([
    [cell('Day', 1, 0), cell('One')], [cell('Two')],
  ])), 'Day\tOne\n\tTwo');
  assert.equal(tableToTsv(table([])), '');
});


test('does not extend merged cells from a header into the table body', () => {
  const header = table([[cell('Header', 1, 5)]]);
  const body = table([[cell('Body')]]);
  assert.equal(tableToTsv({ rows: [...header.rows, ...body.rows] }), 'Header\nBody');
});
