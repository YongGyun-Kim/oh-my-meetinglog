import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { detailFixture, renderDetailWithFixture } from '../../test/detail'
import { ApiError, api } from '../../lib/api'

it('seeks audio and selects the original cited turn', async () => {
  const view = renderDetailWithFixture()
  await userEvent.click(await screen.findByRole('button', { name: '00:01 화자 A 발언 듣기' }))
  expect(view.getByTestId('turn-t1')).toHaveAttribute('aria-current', 'true')
  expect(view.container.querySelector('audio')?.currentTime).toBe(1.25)
  await userEvent.click(screen.getByRole('button', { name: '근거 00:01 화자 A' }))
  expect(view.getByTestId('turn-t1')).toHaveAttribute('aria-current', 'true')
})

it('labels previous analysis after transcript edits', async () => {
  const detail = structuredClone(detailFixture); detail.analysis_stale = true
  renderDetailWithFixture(detail)
  expect(await screen.findByText(/수정 전 전사를 바탕으로/)).toBeInTheDocument()
})

it('preserves an edit draft after a version conflict', async () => {
  vi.spyOn(api, 'edit').mockRejectedValue(new ApiError('다른 창에서 수정되었습니다', 409, 'version_conflict'))
  renderDetailWithFixture()
  await userEvent.click(await screen.findByRole('button', { name: '발언 수정' }))
  const editor = screen.getByLabelText('발언 내용')
  await userEvent.clear(editor); await userEvent.type(editor, '수정한 문장입니다.')
  await userEvent.click(screen.getByRole('button', { name: '수정 저장' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('최신 전사')
  expect(editor).toHaveValue('수정한 문장입니다.')
  expect(api.edit).toHaveBeenCalledWith('rec-1', expect.objectContaining({ base_version_id: 'v1' }))
})

it('renders model content as text and leaves absent facts absent', async () => {
  const detail = structuredClone(detailFixture)
  detail.analysis!.body.overview.summary.text = '<img src=x onerror=alert(1)>'
  const view = renderDetailWithFixture(detail)
  await waitFor(() => expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument())
  expect(view.container.querySelector('img')).toBeNull()
  expect(screen.queryByText('담당자 미정')).not.toBeInTheDocument()
})
