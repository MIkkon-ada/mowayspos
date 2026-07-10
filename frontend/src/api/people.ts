import { apiGet, apiPost, apiPut, apiDelete } from './client'
import type { Person } from '../types'

export type PersonPayload = {
  name: string
  system_role?: string
  department?: string
  is_active?: boolean
  is_admin?: boolean
}

export function fetchPeople(): Promise<Person[]> {
  return apiGet<Person[]>('/api/people')
}

export function createPerson(payload: PersonPayload): Promise<Person> {
  return apiPost<Person>('/api/people', payload)
}

export function updatePerson(id: number, payload: PersonPayload): Promise<Person> {
  return apiPut<Person>(`/api/people/${id}`, payload)
}

export function deletePerson(id: number): Promise<{ ok: boolean }> {
  return apiDelete(`/api/people/${id}`)
}

export type BatchPersonItem = { name: string; role?: string; system_role?: string; department?: string; contact?: string }
export type BatchCreateResult = { created: number; skipped: number; skipped_names: string[]; created_names: string[] }

export function batchCreatePeople(people: BatchPersonItem[]): Promise<BatchCreateResult> {
  return apiPost<BatchCreateResult>('/api/people/batch', { people })
}
