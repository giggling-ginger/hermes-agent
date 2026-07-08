/**
 * Unit tests for the pure zoom helpers: clamping garbage input, the
 * percent <-> zoom-level conversion the settings UI relies on, and the
 * roundtrip stability of the preset percentages.
 */

const test = require('node:test')
const assert = require('node:assert/strict')

const {
  ZOOM_STORAGE_KEY,
  clampZoomLevel,
  createZoomStateCache,
  parseStoredZoomLevel,
  percentToZoomLevel,
  serializeZoomLevel,
  zoomLevelToPercent
} = require('./zoom.cjs')

test('storage key stays stable so persisted zoom survives upgrades', () => {
  assert.equal(ZOOM_STORAGE_KEY, 'hermes:desktop:zoomLevel')
})

test('clampZoomLevel rejects garbage and enforces bounds', () => {
  assert.equal(clampZoomLevel(NaN), 0)
  assert.equal(clampZoomLevel(Infinity), 0)
  assert.equal(clampZoomLevel(undefined), 0)
  assert.equal(clampZoomLevel('2'), 0)
  assert.equal(clampZoomLevel(0.3), 0.3)
  assert.equal(clampZoomLevel(-42), -9)
  assert.equal(clampZoomLevel(42), 9)
})

test('level 0 is exactly 100 percent', () => {
  assert.equal(zoomLevelToPercent(0), 100)
  assert.equal(percentToZoomLevel(100), 0)
})

test('percentToZoomLevel rejects garbage', () => {
  assert.equal(percentToZoomLevel(NaN), 0)
  assert.equal(percentToZoomLevel(0), 0)
  assert.equal(percentToZoomLevel(-50), 0)
  assert.equal(percentToZoomLevel(undefined), 0)
})

test('stored zoom serializes and restores the 110 percent preset', () => {
  const level = percentToZoomLevel(110)
  const stored = serializeZoomLevel(level)

  assert.equal(zoomLevelToPercent(parseStoredZoomLevel(stored)), 110)
})

test('missing stored zoom leaves the app at the default 100 percent', () => {
  assert.equal(parseStoredZoomLevel(null), null)
  assert.equal(zoomLevelToPercent(0), 100)
})

test('cached user zoom wins across reload before stale storage can reset it', () => {
  const win = {}
  const cache = createZoomStateCache(new Map())
  const zoom110 = percentToZoomLevel(110)

  cache.set(win, zoom110)

  assert.equal(zoomLevelToPercent(cache.resolve(win, serializeZoomLevel(0))), 110)
})

test('intentional reset from 110 back to 100 updates the cached source of truth', () => {
  const win = {}
  const cache = createZoomStateCache(new Map())

  cache.set(win, percentToZoomLevel(110))
  cache.set(win, percentToZoomLevel(100))

  assert.equal(zoomLevelToPercent(cache.resolve(win, serializeZoomLevel(percentToZoomLevel(110)))), 100)
})

test('preset percentages roundtrip within rounding', () => {
  for (const percent of [90, 100, 110, 125, 150, 175]) {
    assert.equal(zoomLevelToPercent(percentToZoomLevel(percent)), percent)
  }
})

test('conversion is monotonic across the preset range', () => {
  const levels = [90, 100, 110, 125, 150, 175].map(percentToZoomLevel)
  for (let i = 1; i < levels.length; i++) {
    assert.ok(levels[i] > levels[i - 1])
  }
})

test('extreme percentages clamp to the level bounds', () => {
  assert.equal(percentToZoomLevel(1), -9)
  assert.equal(percentToZoomLevel(1_000_000), 9)
})
