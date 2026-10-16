import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { api } from '../../lib/api'
import { SettingsPage } from './SettingsPage'

it('saves an explicit mode and reports unverified engines honestly', async () => {
  const settings = { mode: 'local_only' as const, api_configured: true, media_tools_ready: true, engines: [{ name: 'asr', repo_id: 'local-model', ready: true, quality: 'unverified' }] }
  vi.spyOn(api, 'settings').mockResolvedValue(settings)
  const update = vi.spyOn(api, 'updateMode').mockResolvedValue({ ...settings, mode: 'auto' })
  render(<SettingsPage />)
  await userEvent.click(await screen.findByLabelText('자동 선택'))
  await waitFor(() => expect(update).toHaveBeenCalledWith('auto'))
  expect(screen.getByText('정확도 미검증')).toBeInTheDocument()
  expect(screen.queryByLabelText('API 키')).not.toBeInTheDocument()
})
