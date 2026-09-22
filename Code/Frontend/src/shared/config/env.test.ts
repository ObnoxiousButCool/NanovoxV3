import { afterEach, describe, expect, it } from 'vitest'

import { getConfig, readConfig, resetConfigCache, type ConfigSource } from '@/shared/config/env'

const VALID: ConfigSource = {
  VITE_API_BASE_URL: 'http://api.test/api/v1',
  VITE_APP_NAME: 'NanoVox Insights',
}

describe('readConfig', () => {
  it('reads a valid configuration', () => {
    const config = readConfig(VALID)

    expect(config).toEqual({
      apiBaseUrl: 'http://api.test/api/v1',
      appName: 'NanoVox Insights',
    })
  })

  it('accepts a root-relative base URL', () => {
    const config = readConfig({ ...VALID, VITE_API_BASE_URL: '/api/v1' })

    expect(config.apiBaseUrl).toBe('/api/v1')
  })

  it('strips a trailing slash from the base URL', () => {
    const config = readConfig({ ...VALID, VITE_API_BASE_URL: 'http://api.test/api/v1/' })

    expect(config.apiBaseUrl).toBe('http://api.test/api/v1')
  })

  it('throws when the base URL is missing', () => {
    expect(() => readConfig({ ...VALID, VITE_API_BASE_URL: '' })).toThrow('VITE_API_BASE_URL')
  })

  it('throws when the base URL is neither absolute nor root-relative', () => {
    expect(() => readConfig({ ...VALID, VITE_API_BASE_URL: 'not a url' })).toThrow(
      'VITE_API_BASE_URL must be an absolute URL',
    )
  })

  it('throws when the app name is missing', () => {
    expect(() => readConfig({ ...VALID, VITE_APP_NAME: '   ' })).toThrow('VITE_APP_NAME')
  })
})

describe('getConfig', () => {
  afterEach(() => {
    resetConfigCache()
  })

  it('reads the real Vite environment, pinned for tests in vite.config.ts', () => {
    expect(getConfig()).toEqual({
      apiBaseUrl: 'http://api.test/api/v1',
      appName: 'NanoVox Insights',
    })
  })

  it('caches the result across calls', () => {
    expect(getConfig()).toBe(getConfig())
  })
})
