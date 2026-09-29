import { useEffect, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowUpRight, Check, ChevronRight,
  CircleHelp, Clock3, Database, Gauge, GitBranch, HardDrive, Layers3, LoaderCircle,
  Play, RotateCcw, Search, ShieldAlert, Siren, Sparkles, Wrench, X,
} from 'lucide-react'

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

type Attempt = { action: string; outcome: 'failed' | 'partial' | 'successful'; details: string; duration_minutes?: number | null }
type ResolutionStatus = 'successful' | 'partial' | 'failed'
type ResolutionModalState = { open: boolean; mode: 'simulate' | 'resolve'; status: ResolutionStatus | null; details: string }
type Incident = { incident_id: string; service: string; symptoms: string; environment: string; deployment_version: string; evidence: string[] }
type ToolResult = { name: string; arguments: Record<string, unknown>; result: Record<string, unknown> | null; error: string | null }
type Memory = { id: string; text: string; type: string | null; context: string | null; metadata: Record<string, string>; rank: number }
type Investigation = { incident: Incident; summary: string; probable_cause: string; recommendation: string; confidence: string; planner_mode: string; memory_mode: string; tool_results: ToolResult[]; historical_memories: Memory[]; memory_status: string }
type IncidentRow = { incident_id: string; service: string; environment: string; status: string; updated_at: string; request: Incident; investigation?: Investigation | null; resolution?: { lesson: string; root_cause: string; remediation_attempts: Attempt[] } | null }
type Dashboard = { incident_total: number; active_incidents: number; remembered_incidents: number; remediation_counts: Record<string, number>; incidents: IncidentRow[]; remediation_attempts: Array<Attempt & { incident_id: string; created_at: string }>; investigation_actions: Array<{ incident_id: string; tool_name: string; result: Record<string, unknown> | null; created_at: string }>; evaluation_runs: Array<{ id: string; mode: string; latency_ms: number; result: Record<string, unknown>; created_at: string }> }
type ServiceHealth = { service: string; status: string; replicas_ready: number; replicas_total: number; uptime_percent: number }
type EvaluationRun = { run_id: string; mode: string; latency_ms: number; relevant_memories_returned: number; failed_approach_recalled: boolean; successful_approach_recalled: boolean; diagnosis: string; recommendation: string; planner_mode: string }
type ResolutionRecord = {
  status: ResolutionStatus
  details: string
  rootCause: string
  lesson: string
  telemetryDelta: string
  confirmed: boolean
  created_at: string
}

const navigation = [
  { id: 'overview', label: 'Overview', icon: Gauge },
  { id: 'incidents', label: 'Incidents', icon: Siren },
  { id: 'timeline', label: 'Timeline', icon: Clock3 },
  { id: 'memory', label: 'Memory', icon: Layers3 },
  { id: 'systems', label: 'System health', icon: Activity },
  { id: 'evaluation', label: 'Evaluation', icon: GitBranch },
] as const

type Page = typeof navigation[number]['id']

const defaultIncident: Incident = {
  incident_id: `INC-${new Date().toISOString().slice(2, 10).replaceAll('-', '')}-01`,
  service: 'checkout-service',
  symptoms: 'Checkout API returning 503 errors; database pool is full',
  environment: 'staging',
  deployment_version: 'checkout-2.14.3',
  evidence: [],
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`)
  return body as T
}

function App() {
  const [page, setPage] = useState<Page>('overview')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [health, setHealth] = useState<ServiceHealth[]>([])
  const [incident, setIncident] = useState<Incident>(defaultIncident)
  const [investigation, setInvestigation] = useState<Investigation | null>(null)
  const [attempts, setAttempts] = useState<Attempt[]>([])
  const [action, setAction] = useState('Restart checkout service')
  const [rootCause, setRootCause] = useState('Database connection pool exhaustion')
  const [lesson, setLesson] = useState('A restart only masks pool exhaustion; increasing pool capacity resolved it.')
  const [evaluationInput, setEvaluationInput] = useState<Incident>(defaultIncident)
  const [evaluation, setEvaluation] = useState<EvaluationRun[] | null>(null)
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [resolutionModal, setResolutionModal] = useState<ResolutionModalState>({ open: false, mode: 'resolve', status: null, details: '' })
  const [resolutionLog, setResolutionLog] = useState<Record<string, ResolutionRecord>>({})
  const [hindsightConfirmedIds, setHindsightConfirmedIds] = useState<Record<string, boolean>>({})

  async function refresh() {
    const [nextDashboard, nextHealth] = await Promise.all([
      api<Dashboard>('/api/dashboard'),
      api<ServiceHealth[]>('/api/system-health'),
    ])
    setDashboard(nextDashboard)
    setHealth(nextHealth)
  }

  useEffect(() => {
    refresh().catch((reason: Error) => setError(reason.message))
  }, [])

  async function run(actionName: string, operation: () => Promise<void>) {
    setBusy(actionName)
    setError('')
    setNotice('')
    try {
      await operation()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unexpected request error')
    } finally {
      setBusy('')
    }
  }

  async function investigate() {
    await run('investigate', async () => {
      const result = await api<Investigation>('/api/incidents/investigate', { method: 'POST', body: JSON.stringify(incident) })
      setInvestigation(result)
      setPage('incidents')
      await refresh()
    })
  }

  async function simulateAction(statusOverride?: ResolutionStatus, detailsOverride?: string) {
    const chosenStatus = statusOverride ?? 'successful'
    const chosenDetails = detailsOverride?.trim() || 'Follow-up action recorded during the guided remediation workflow.'

    await run('remediate', async () => {
      const result = await api<{ attempt: Attempt }>('/api/incidents/simulate-remediation', {
        method: 'POST', body: JSON.stringify({ incident, action }),
      })
      const mergedAttempt: Attempt = {
        ...result.attempt,
        outcome: chosenStatus,
        details: chosenDetails,
        duration_minutes: result.attempt.duration_minutes ?? (chosenStatus === 'successful' ? 12 : chosenStatus === 'partial' ? 7 : 4),
      }
      setAttempts((current) => [...current, mergedAttempt])
      setResolutionLog((current) => ({
        ...current,
        [incident.incident_id]: {
          status: chosenStatus,
          details: chosenDetails,
          rootCause: rootCause || 'Manual remediation note recorded before resolution.',
          lesson: lesson || 'Incident reviewed and documented.',
          telemetryDelta: `Error Rate: ${incident.symptoms.includes('503') ? '87%' : 'current'} -> ${chosenStatus === 'successful' ? '0%' : chosenStatus === 'partial' ? '15%' : '87%'}, Waiters: 42 -> ${chosenStatus === 'successful' ? '0' : chosenStatus === 'partial' ? '6' : '42'}`,
          confirmed: false,
          created_at: new Date().toISOString(),
        },
      }))
      await refresh()
    })
  }

  async function resolveIncident(statusOverride?: ResolutionStatus, detailsOverride?: string) {
    if (!attempts.length) {
      setError('Record at least one simulated remediation outcome before resolving.')
      return
    }
    const chosenStatus = statusOverride ?? 'successful'
    const chosenDetails = detailsOverride?.trim() || 'Manual resolution notes were recorded during the final outcome update.'
    const recordedAttempts = attempts.map((attempt, index) => index === attempts.length - 1
      ? { ...attempt, details: `${attempt.details} Resolution notes: ${chosenDetails}` }
      : attempt)

    await run('resolve', async () => {
      const result = await api<{ retained: boolean; message: string }>('/api/incidents/resolve', {
        method: 'POST',
        body: JSON.stringify({ incident, root_cause: rootCause, remediation_attempts: recordedAttempts, lesson, recovery_time_minutes: recordedAttempts.find((item) => item.outcome === 'successful')?.duration_minutes ?? null }),
      })
      setNotice(result.message)
      setAttempts([])
      setResolutionLog((current) => ({
        ...current,
        [incident.incident_id]: {
          status: chosenStatus,
          details: chosenDetails,
          rootCause: rootCause || 'Manual root cause note recorded.',
          lesson: lesson || 'Logged incident resolution outcome.',
          telemetryDelta: `Error Rate: 87% -> ${chosenStatus === 'successful' ? '0%' : chosenStatus === 'partial' ? '12%' : '87%'}, Waiters: 42 -> ${chosenStatus === 'successful' ? '0' : chosenStatus === 'partial' ? '7' : '42'}`,
          confirmed: true,
          created_at: new Date().toISOString(),
        },
      }))
      setHindsightConfirmedIds((current) => ({ ...current, [incident.incident_id]: true }))
      await refresh()
    })
  }

  async function seedDemo(reset = false) {
    await run(reset ? 'reset' : 'seed', async () => {
      const result = await api<{ seeded_incidents: number; bank_id: string; note: string }>(reset ? '/api/demo/reset' : '/api/demo/seed', { method: 'POST' })
      setNotice(`${result.seeded_incidents} resolved incidents retained in ${result.bank_id}. ${result.note}`)
      await refresh()
    })
  }

  async function runEvaluation() {
    await run('evaluation', async () => {
      const result = await api<{ runs: EvaluationRun[] }>('/api/evaluation/run', { method: 'POST', body: JSON.stringify({ incident: evaluationInput }) })
      setEvaluation(result.runs)
      await refresh()
    })
  }

  const nav = (id: Page) => setPage(id)
  const isLoading = Boolean(busy)
  const lastIncident = dashboard?.incidents.find((item) => item.investigation)?.investigation ?? undefined
  const storedLessons = dashboard?.incidents.filter((item) => item.resolution?.lesson) ?? []
  const incidentsByOutcome: Record<ResolutionStatus, Set<string>> = {
    successful: new Set(), partial: new Set(), failed: new Set(),
  }
  // Count distinct incidents that had at least one remediation attempt of
  // each outcome. A single incident can contribute to multiple status totals.
  dashboard?.incidents.forEach((item) => {
    item.resolution?.remediation_attempts.forEach((attempt) => incidentsByOutcome[attempt.outcome].add(item.incident_id))
  })
  dashboard?.remediation_attempts.forEach((attempt) => incidentsByOutcome[attempt.outcome].add(attempt.incident_id))
  Object.entries(resolutionLog).forEach(([incidentId, record]) => incidentsByOutcome[record.status].add(incidentId))
  const statusCounts = {
    successful: incidentsByOutcome.successful.size,
    partial: incidentsByOutcome.partial.size,
    failed: incidentsByOutcome.failed.size,
  }

  const openResolutionModal = (mode: 'simulate' | 'resolve') => {
    setResolutionModal({ open: true, mode, status: null, details: '' })
  }

  const submitResolutionModal = () => {
    if (!resolutionModal.status || !resolutionModal.details.trim()) {
      setError('Select an outcome status and provide remediation details before proceeding.')
      return
    }

    const currentStatus = resolutionModal.status
    const details = resolutionModal.details.trim()

    setError('')
    setResolutionModal({ open: false, mode: 'resolve', status: null, details: '' })

    if (resolutionModal.mode === 'simulate') {
      void simulateAction(currentStatus, details)
      return
    }

    void resolveIncident(currentStatus, details)
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" onClick={() => nav('overview')}>
          <span className="brand-mark"><Activity size={19} strokeWidth={2.5} /></span>
          <span><strong>shadowops</strong><small>INCIDENT RESPONSE</small></span>
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button className={`nav-item ${page === id ? 'active' : ''}`} data-nav={id} key={id} onClick={() => nav(id)}>
              <Icon size={17} strokeWidth={1.9} /><span>{label}</span>
              {id === 'incidents' && dashboard?.active_incidents ? <b className="nav-count">{dashboard.active_incidents}</b> : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <div className="connection-card">
          <div className="connection-title"><span className="live-dot" />HINDSIGHT CLOUD</div>
          <p>Memory retrieval is live and evidence-linked.</p>
          <button onClick={() => nav('memory')}>View memory <ChevronRight size={14} /></button>
        </div>
        <div className="sidebar-footer"><span className="avatar">SO</span><span><b>ShadowOps team</b><small>Demo workspace</small></span><CircleHelp size={16} /></div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Operations</span><ChevronRight size={14} /><strong>{navigation.find((item) => item.id === page)?.label}</strong></div>
          <div className="topbar-actions"><span className="environment-chip"><span /> STAGING SIMULATION</span><button className="icon-button" title="Refresh data" onClick={() => run('refresh', refresh)}><RotateCcw size={16} /></button></div>
        </header>

        <div className="page-content">
          {(error || notice) && <div className={`notice ${error ? 'notice-error' : 'notice-success'}`} role="status">{error ? <AlertTriangle size={16} /> : <Check size={16} />}{error || notice}<button title="Dismiss" onClick={() => { setError(''); setNotice('') }}><X size={15} /></button></div>}

          {page === 'overview' && <Overview dashboard={dashboard} health={health} busy={busy} onSeed={() => seedDemo()} onReset={() => seedDemo(true)} onInvestigate={() => { setIncident(defaultIncident); setAttempts([]); setInvestigation(null); void investigate() }} resolutionCounts={statusCounts} />}
          {page === 'incidents' && <IncidentWorkspace incident={incident} setIncident={setIncident} investigation={investigation} attempts={attempts} action={action} setAction={setAction} rootCause={rootCause} setRootCause={setRootCause} lesson={lesson} setLesson={setLesson} busy={busy} onInvestigate={investigate} onSimulate={() => openResolutionModal('simulate')} onResolve={() => openResolutionModal('resolve')} />}
          {page === 'timeline' && <Timeline dashboard={dashboard} />}
          {page === 'memory' && <MemoryView dashboard={dashboard} lastIncident={lastIncident} lessons={storedLessons} busy={busy} onSeed={() => seedDemo()} onReset={() => seedDemo(true)} resolutionLog={resolutionLog} hindsightConfirmedIds={hindsightConfirmedIds} resolutionCounts={statusCounts} />}
          {page === 'systems' && <SystemHealth health={health} />}
          {page === 'evaluation' && <EvaluationView incident={evaluationInput} setIncident={setEvaluationInput} runs={evaluation} busy={busy} onRun={runEvaluation} />}
        </div>
        <footer className="page-footer"><span>SHADOWOPS CONTROL PLANE</span><span>SIMULATED SERVICES · REAL HINDSIGHT MEMORY</span><span>BUILD 0.2</span></footer>
      </main>
      {resolutionModal.open && <ResolutionModal modal={resolutionModal} onClose={() => setResolutionModal((current) => ({ ...current, open: false }))} onChange={(next) => setResolutionModal((current) => ({ ...current, ...next }))} onSubmit={submitResolutionModal} />}
      {isLoading && <div className="busy-indicator"><LoaderCircle size={15} className="spin" />{busy === 'investigate' ? 'Investigating incident' : busy === 'evaluation' ? 'Running comparison' : busy === 'seed' || busy === 'reset' ? 'Preparing demo memory' : busy === 'resolve' ? 'Recording outcome in Hindsight' : 'Updating'}</div>}
    </div>
  )
}

function PageHeading({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: React.ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{actions && <div className="heading-actions">{actions}</div>}</div>
}

function Stat({ label, value, detail, icon: Icon, tone = '' }: { label: string; value: string | number; detail: string; icon: typeof Activity; tone?: string }) {
  return <article className="stat-block"><div className={`stat-icon ${tone}`}><Icon size={17} /></div><div className="stat-copy"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div></article>
}

function Overview({ dashboard, health, busy, onSeed, onReset, onInvestigate, resolutionCounts }: { dashboard: Dashboard | null; health: ServiceHealth[]; busy: string; onSeed: () => void; onReset: () => void; onInvestigate: () => void; resolutionCounts: { successful: number; partial: number; failed: number } }) {
  return <>
    <PageHeading eyebrow="TUESDAY, SEPTEMBER 29, 2026 · LIVE SIMULATION" title="Incident overview" description="A running view of service health, active response work, and what the organization has learned." actions={<><button className="button button-secondary" disabled={Boolean(busy)} onClick={onSeed}><Database size={15} />Seed Hindsight</button><button className="button button-secondary" disabled={Boolean(busy)} onClick={onReset}><RotateCcw size={15} />Reset demo</button><button className="button button-primary" onClick={onInvestigate}><Siren size={15} />New investigation</button></>} />
    <section className="stat-grid">
      <Stat label="Incidents with successful outcomes" value={resolutionCounts.successful} detail="At least one successful remediation" icon={Check} tone="green" />
      <Stat label="Incidents with partial outcomes" value={resolutionCounts.partial} detail="At least one partial remediation" icon={AlertTriangle} tone="amber" />
      <Stat label="Incidents with failed outcomes" value={resolutionCounts.failed} detail="At least one failed remediation" icon={X} tone="red" />
      <Stat label="Incidents remembered" value={dashboard?.remembered_incidents ?? '—'} detail="Confirmed Hindsight writes" icon={Database} tone="blue" />
    </section>
    <div className="overview-grid">
      <section className="panel active-panel">
        <div className="panel-heading"><div><div className="eyebrow">RESPONSE QUEUE</div><h2>Active incidents</h2></div><button className="text-button" onClick={() => document.querySelector<HTMLButtonElement>('[data-nav="incidents"]')?.click()}>All incidents <ChevronRight size={14} /></button></div>
        <div className="incident-list">
          {(dashboard?.incidents.filter((item) => item.status !== 'resolved') ?? []).slice(0, 5).map((item) => <div className="incident-row" key={item.incident_id}><span className="severity-dot" /><div className="incident-row-main"><strong>{item.request.symptoms}</strong><small>{item.incident_id} · {item.service} · {item.environment}</small></div><span className="status-pill status-active">Investigating</span><ChevronRight size={16} className="row-chevron" /></div>)}
          {!dashboard?.incidents.some((item) => item.status !== 'resolved') && <div className="empty-inline"><span className="empty-icon"><Check size={17} /></span><div><strong>No active incidents</strong><small>Start an investigation or seed the demo dataset.</small></div></div>}
        </div>
        <div className="panel-footer"><span>Current incident evidence comes from the simulated environment.</span><span className="live-label"><span className="live-dot" />SYNCED</span></div>
      </section>
      <section className="panel service-panel">
        <div className="panel-heading"><div><div className="eyebrow">SIMULATED FLEET</div><h2>Service status</h2></div><button className="icon-button" title="View full system health"><ArrowUpRight size={16} /></button></div>
        <div className="service-list">{health.map((service) => <div className="service-row" key={service.service}><span className={`service-status ${service.status}`} /><span className="service-name">{service.service}</span><span className="replica-count">{service.replicas_ready}/{service.replicas_total}</span><span className={`service-state ${service.status}`}>{service.status}</span></div>)}</div>
        <div className="service-foot"><span><span className="legend-dot healthy" />Healthy</span><span><span className="legend-dot degraded" />Degraded</span><span>Readiness · current</span></div>
      </section>
      <section className="panel learning-panel">
        <div className="panel-heading"><div><div className="eyebrow">ORGANIZATIONAL MEMORY</div><h2>Recent lessons</h2></div><button className="text-button" onClick={() => document.querySelector<HTMLButtonElement>('[data-nav="memory"]')?.click()}>Memory bank <ChevronRight size={14} /></button></div>
        {(dashboard?.incidents.filter((item) => item.resolution?.lesson) ?? []).slice(0, 3).map((item) => <div className="lesson-row" key={item.incident_id}><span className="lesson-mark"><Sparkles size={15} /></span><div><strong>{item.resolution?.lesson}</strong><small>{item.incident_id} · {item.service} · confirmed write</small></div></div>)}
        {!dashboard?.incidents.some((item) => item.resolution?.lesson) && <div className="empty-inline"><span className="empty-icon"><Database size={17} /></span><div><strong>No lessons stored yet</strong><small>Seed the demo to write real incident memories to Hindsight.</small></div></div>}
        <div className="learning-note"><span className="note-line" /><p>Later investigations can retrieve these recorded outcomes. Hindsight memory is never inferred from the app database.</p></div>
      </section>
    </div>
  </>
}

function IncidentWorkspace({ incident, setIncident, investigation, attempts, action, setAction, rootCause, setRootCause, lesson, setLesson, busy, onInvestigate, onSimulate, onResolve }: { incident: Incident; setIncident: (incident: Incident) => void; investigation: Investigation | null; attempts: Attempt[]; action: string; setAction: (value: string) => void; rootCause: string; setRootCause: (value: string) => void; lesson: string; setLesson: (value: string) => void; busy: string; onInvestigate: () => void; onSimulate: () => void; onResolve: () => void }) {
  const updateIncident = (field: keyof Incident, value: string) => setIncident({ ...incident, [field]: value })
  return <>
    <PageHeading eyebrow="INVESTIGATION WORKSPACE" title="Incident response" description="Investigate current signals, compare Hindsight evidence, then record the observed remediation outcome." actions={<button className="button button-primary" disabled={Boolean(busy)} onClick={onInvestigate}><Search size={15} />Run investigation</button>} />
    <div className="workspace-layout">
      <section className="panel workspace-main">
        <div className="panel-heading"><div><div className="eyebrow">CURRENT INCIDENT</div><h2>Incident details</h2></div><span className="status-pill status-active">{investigation ? 'Investigated' : 'Ready'}</span></div>
        <div className="form-grid">
          <label>Incident ID<input value={incident.incident_id} onChange={(event) => updateIncident('incident_id', event.target.value)} /></label>
          <label>Service<select value={incident.service} onChange={(event) => updateIncident('service', event.target.value)}>{['checkout-service', 'payment-service', 'order-service', 'auth-service', 'notification-service'].map((service) => <option key={service}>{service}</option>)}</select></label>
          <label className="field-wide">Symptoms<textarea rows={2} value={incident.symptoms} onChange={(event) => updateIncident('symptoms', event.target.value)} /></label>
          <label>Environment<input value={incident.environment} onChange={(event) => updateIncident('environment', event.target.value)} /></label>
          <label>Deployment version<input value={incident.deployment_version} onChange={(event) => updateIncident('deployment_version', event.target.value)} /></label>
        </div>
        {investigation && <>
          <div className="section-divider"><span>INVESTIGATION TRACE</span><span className="planner-chip">{investigation.planner_mode.replaceAll('_', ' ')}</span></div>
          <div className="tool-trace">{investigation.tool_results.map((tool, index) => <details className="tool-result" key={`${tool.name}-${index}`} open={index < 2}><summary><span className="tool-check">{tool.error ? <X size={12} /> : <Check size={12} />}</span><span>{tool.name}</span><small>{tool.error ? 'error' : 'complete'}</small><ChevronRight size={14} /></summary>{tool.error ? <p>{tool.error}</p> : <pre>{JSON.stringify(tool.result, null, 2)}</pre>}</details>)}</div>
          <div className="diagnosis-block"><div className="diagnosis-label"><ShieldAlert size={15} />PROBABLE CAUSE <span className={`confidence confidence-${investigation.confidence}`}>{investigation.confidence} confidence</span></div><p>{investigation.probable_cause}</p><div className="recommendation"><b>RECOMMENDED NEXT STEP</b><p>{investigation.recommendation}</p></div></div>
          <div className="section-divider"><span>SIMULATE REMEDIATION</span><span className="simulation-label">DETERMINISTIC DEMO</span></div>
          <div className="action-entry"><input value={action} onChange={(event) => setAction(event.target.value)} aria-label="Remediation action" /><button className="button button-secondary" disabled={Boolean(busy)} onClick={onSimulate}><Wrench size={15} />Run action</button></div>
          {attempts.map((attempt, index) => <div className="attempt-row" key={`${attempt.action}-${index}`}><span className={`outcome-icon ${attempt.outcome}`}>{attempt.outcome === 'successful' ? <Check size={14} /> : attempt.outcome === 'failed' ? <X size={14} /> : <AlertTriangle size={14} />}</span><div><strong>{attempt.action}</strong><small>{attempt.details}</small></div><span className={`outcome-label ${attempt.outcome}`}>{attempt.outcome}</span></div>)}
          {attempts.length > 0 && <div className="resolution-form"><div className="section-divider"><span>RESOLUTION LEARNING</span><span>WRITES TO HINDSIGHT</span></div><label>Confirmed root cause<input value={rootCause} onChange={(event) => setRootCause(event.target.value)} /></label><label>Lesson learned<textarea rows={2} value={lesson} onChange={(event) => setLesson(event.target.value)} /></label><button className="button button-primary" disabled={Boolean(busy)} onClick={onResolve}><Database size={15} />Resolve and retain outcome</button></div>}
        </>}
        {!investigation && <div className="initial-state"><div className="initial-mark"><Search size={20} /></div><strong>Ready to investigate</strong><p>Run an investigation to inspect simulated service signals, then retrieve relevant Hindsight history.</p><button className="button button-primary" onClick={onInvestigate}><Play size={14} />Start investigation</button></div>}
      </section>
      <aside className="panel memory-aside">
        <div className="panel-heading"><div><div className="eyebrow">HINDSIGHT MEMORY</div><h2>Historical evidence</h2></div><span className={`memory-state ${investigation?.memory_status || 'idle'}`}><span />{investigation?.memory_status === 'available' ? 'Recalled' : investigation?.memory_status === 'empty' ? 'No match' : 'Awaiting query'}</span></div>
        {investigation?.historical_memories.length ? investigation.historical_memories.map((memory) => <MemoryCard memory={memory} key={memory.id} />) : <div className="memory-empty"><Database size={19} /><strong>{investigation ? 'No related memory returned' : 'Memory appears after recall'}</strong><p>{investigation ? 'Hindsight returned no matching facts for this service. The recommendation uses current tool evidence only.' : 'Run the investigation to query the configured Hindsight bank.'}</p></div>}
        <div className="memory-aside-foot"><span>Only facts returned by Hindsight appear here.</span><a href="https://hindsight.vectorize.io/" target="_blank" rel="noreferrer">API docs <ArrowUpRight size={12} /></a></div>
      </aside>
    </div>
  </>
}

function ResolutionModal({ modal, onClose, onChange, onSubmit }: { modal: ResolutionModalState; onClose: () => void; onChange: (next: Partial<ResolutionModalState>) => void; onSubmit: () => void }) {
  const statusOptions: Array<{ value: ResolutionStatus; label: string; className: string }> = [
    { value: 'successful', label: 'SUCCESSFUL', className: 'successful' },
    { value: 'partial', label: 'PARTIAL', className: 'partial' },
    { value: 'failed', label: 'FAILED', className: 'failed' },
  ]

  return <div className="modal-backdrop" onClick={onClose}><div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="resolution-title" onClick={(event) => event.stopPropagation()}><div className="modal-header"><h3 id="resolution-title">{modal.mode === 'simulate' ? 'Simulate remediation outcome' : 'Resolve and retain outcome'}</h3><button className="modal-close" type="button" aria-label="Close" onClick={onClose}>×</button></div><div className="modal-body"><div><div className="modal-status-row" role="group" aria-label="Outcome status">{statusOptions.map((option) => <button key={option.value} type="button" aria-pressed={modal.status === option.value} className={`status-choice ${option.className} ${modal.status === option.value ? 'active' : ''}`} onClick={() => onChange({ status: option.value })}>{option.label}</button>)}</div></div><label>
        Remediation Details / Root Cause Explanation
        <textarea value={modal.details} onChange={(event) => onChange({ details: event.target.value })} placeholder="Why did it succeed or fail? What exact steps fixed it?" />
      </label></div><div className="modal-footer"><button className="button button-secondary" type="button" onClick={onClose}>Cancel</button><button className="button button-primary" type="button" onClick={onSubmit} disabled={!modal.status || !modal.details.trim()}>Confirm</button></div></div></div>
}

function MemoryCard({ memory, resolutionLog = {}, hindsightConfirmedIds = {} }: { memory: Memory; resolutionLog?: Record<string, ResolutionRecord>; hindsightConfirmedIds?: Record<string, boolean> }) {
  const incidentId = memory.metadata.incident_id || memory.id
  const localRecord = resolutionLog[incidentId]
  const rawStatus = (memory.metadata.remediation_outcome || localRecord?.status || '').toLowerCase()
  const status = (['successful', 'partial', 'failed'].includes(rawStatus) ? rawStatus : null) as ResolutionStatus | null
  const rootCauseSummary = memory.metadata.root_cause_summary || memory.metadata.root_cause || localRecord?.rootCause || 'The remediation outcome was recorded and saved to the shared Hindsight insight record.'
  const telemetryDelta = memory.metadata.telemetry_delta || localRecord?.telemetryDelta || 'Error Rate: — -> —, Waiters: — -> —'
  const details = memory.metadata.remediation_details || memory.metadata.user_notes || localRecord?.details || 'User and agent notes are available in the incident workflow logs.'
  const [expanded, setExpanded] = useState(false)

  return <article className="memory-card"><div className="memory-card-head"><span className="memory-rank">#{memory.rank}</span><span className="memory-id">{incidentId}</span>{status && <span className={`outcome-label ${status}`}>{status.toUpperCase()}</span>}{hindsightConfirmedIds[incidentId] && <span className="receipt-tag-inline"><Check size={11} />Hindsight write confirmed</span>}</div><p>{memory.text}</p>{memory.metadata.remediation_action && <div className="memory-action"><Wrench size={13} /><span>{memory.metadata.remediation_action}</span></div>}<button className="memory-toggle" type="button" aria-expanded={expanded} onClick={() => setExpanded((current) => !current)}>{expanded ? 'Hide details' : 'Show details / Why this outcome?'}</button>{expanded && <div className="memory-details"><div><small>Root cause summary</small><p>{rootCauseSummary}</p></div><div><small>Telemetry delta</small><p>{telemetryDelta}</p></div><div><small>Resolution notes</small><p>{details}</p></div></div>}<div className="memory-meta"><span>{memory.type || 'fact'}</span><span>{memory.metadata.service || memory.context || 'Hindsight result'}</span><span>Ranked evidence</span></div></article>
}

function Timeline({ dashboard }: { dashboard: Dashboard | null }) {
  const items = dashboard?.remediation_attempts ?? []
  return <>
    <PageHeading eyebrow="INCIDENT HISTORY" title="Learning timeline" description="Recorded investigation actions, remediation outcomes, and confirmed memory writes." />
    <section className="panel timeline-panel"><div className="panel-heading"><div><div className="eyebrow">APP-RECORDED EVENTS</div><h2>Incident progression</h2></div><span className="status-pill">{items.length} outcomes</span></div>
      {!items.length && <EmptyMessage title="No recorded timeline yet" text="Seed the deterministic incident set or investigate and resolve an incident." />}
      {items.map((item, index) => <div className="timeline-item" key={`${item.incident_id}-${index}`}><div className="timeline-rail"><span className={`timeline-node ${item.outcome}`} /><span className="timeline-line" /></div><div className="timeline-copy"><div className="timeline-meta"><strong>{item.incident_id}</strong><time>{new Date(item.created_at).toLocaleString()}</time></div><p>{item.action}</p><small>{item.details}</small></div><span className={`outcome-label ${item.outcome}`}>{item.outcome}</span></div>)}
    </section>
  </>
}

function MemoryView({ dashboard, lastIncident, lessons, busy, onSeed, onReset, resolutionLog = {}, hindsightConfirmedIds = {}, resolutionCounts }: { dashboard: Dashboard | null; lastIncident?: Investigation; lessons: IncidentRow[]; busy: string; onSeed: () => void; onReset: () => void; resolutionLog?: Record<string, ResolutionRecord>; hindsightConfirmedIds?: Record<string, boolean>; resolutionCounts: { successful: number; partial: number; failed: number } }) {
  return <>
    <PageHeading eyebrow="PERSISTENT ORGANIZATIONAL LEARNING" title="Hindsight memory" description="Write receipts and lesson summaries tracked by ShadowOps, plus facts returned from actual recall calls." actions={<><button className="button button-secondary" disabled={Boolean(busy)} onClick={onSeed}><Database size={15} />Seed 10 incidents</button><button className="button button-secondary" disabled={Boolean(busy)} onClick={onReset}><RotateCcw size={15} />Reset + reseed</button></>} />
    <div className="stat-grid memory-stats"><Stat label="Incidents with successful outcomes" value={resolutionCounts.successful} detail="At least one successful remediation" icon={Check} tone="green" /><Stat label="Incidents with partial outcomes" value={resolutionCounts.partial} detail="At least one partial remediation" icon={AlertTriangle} tone="amber" /><Stat label="Incidents with failed outcomes" value={resolutionCounts.failed} detail="At least one failed remediation" icon={X} tone="red" /><Stat label="Confirmed incident writes" value={dashboard?.remembered_incidents ?? 0} detail="Distinct successful Hindsight writes" icon={Database} tone="blue" /></div>
    <div className="memory-page-grid"><section className="panel"><div className="panel-heading"><div><div className="eyebrow">LATEST LIVE RECALL</div><h2>Returned Hindsight facts</h2></div>{lastIncident && <span className="planner-chip">{lastIncident.historical_memories.length} facts</span>}</div>{lastIncident?.historical_memories.length ? lastIncident.historical_memories.map((memory) => <MemoryCard memory={memory} key={memory.id} resolutionLog={resolutionLog} hindsightConfirmedIds={hindsightConfirmedIds} />) : <EmptyMessage title="No recall results to display" text="This area is populated only from actual facts returned by an investigation recall." />}</section>
      <section className="panel"><div className="panel-heading"><div><div className="eyebrow">APP-DERIVED LESSONS</div><h2>Resolved incident lessons</h2></div></div>{lessons.length ? lessons.map((item) => <SavedLessonCard key={item.incident_id} item={item} localRecord={resolutionLog[item.incident_id]} confirmed={Boolean(hindsightConfirmedIds[item.incident_id] || item.resolution)} />) : <EmptyMessage title="No confirmed lessons" text="Resolve an incident or seed the demo to create actual Hindsight write receipts." />}</section></div>
    <div className="memory-disclaimer"><ShieldAlert size={15} /><span>Receipt totals are app-tracked successful writes. Recalled facts above are from Hindsight responses. They are different measures.</span></div>
  </>
}

function SavedLessonCard({ item, localRecord, confirmed }: { item: IncidentRow; localRecord?: ResolutionRecord; confirmed: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const outcome = localRecord?.status || item.resolution?.remediation_attempts.at(-1)?.outcome
  const details = localRecord?.details || item.resolution?.remediation_attempts.map((attempt) => `${attempt.action}: ${attempt.details}`).join(' · ') || 'No remediation notes saved.'
  const telemetry = localRecord?.telemetryDelta || 'Telemetry delta was not included in the stored incident record.'
  return <article className="lesson-record"><div className="lesson-record-top"><span>{item.incident_id}</span>{outcome && <span className={`outcome-label ${outcome}`}>{outcome.toUpperCase()}</span>}{confirmed && <span className="receipt-tag"><Check size={12} />Hindsight write confirmed</span>}</div><strong>{item.resolution?.lesson}</strong><small>{item.resolution?.root_cause} · {item.service}</small><button className="memory-toggle" type="button" aria-expanded={expanded} onClick={() => setExpanded((current) => !current)}>{expanded ? 'Hide details' : 'Show details / Why this outcome?'}</button>{expanded && <div className="memory-details"><div><small>Root cause summary</small><p>{localRecord?.rootCause || item.resolution?.root_cause}</p></div><div><small>Telemetry delta</small><p>{telemetry}</p></div><div><small>Resolution notes</small><p>{details}</p></div></div>}</article>
}

function SystemHealth({ health }: { health: ServiceHealth[] }) {
  return <><PageHeading eyebrow="SIMULATED TELEMETRY" title="System health" description="Fixture-backed service readiness for the deterministic incident environment." /><section className="panel"><div className="panel-heading"><div><div className="eyebrow">SERVICE INVENTORY</div><h2>Readiness snapshot</h2></div><span className="simulation-label">SIMULATED</span></div><div className="health-table"><div className="health-head"><span>Service</span><span>Status</span><span>Ready replicas</span><span>Uptime</span><span>Signal</span></div>{health.map((service) => <div className="health-row" key={service.service}><strong>{service.service}</strong><span className={`health-status ${service.status}`}>{service.status}</span><span>{service.replicas_ready} / {service.replicas_total}</span><span>{service.uptime_percent}%</span><span className="health-bar"><i className={service.status} style={{ width: `${service.uptime_percent}%` }} /></span></div>)}</div></section></>
}

function EvaluationView({ incident, setIncident, runs, busy, onRun }: { incident: Incident; setIncident: (value: Incident) => void; runs: EvaluationRun[] | null; busy: string; onRun: () => void }) {
  return <><PageHeading eyebrow="CONTROLLED COMPARISON" title="Memory evaluation" description="Run the same incident and current-signal tools with recall disabled and with real Hindsight recall enabled." actions={<button className="button button-primary" disabled={Boolean(busy)} onClick={onRun}><Play size={14} />Run comparison</button>} />
    <section className="panel eval-input"><div className="panel-heading"><div><div className="eyebrow">FIXED INPUT</div><h2>Incident under test</h2></div><span className="simulation-label">SAME INPUT · BOTH RUNS</span></div><div className="form-grid"><label>Incident ID<input value={incident.incident_id} onChange={(event) => setIncident({ ...incident, incident_id: event.target.value })} /></label><label>Service<select value={incident.service} onChange={(event) => setIncident({ ...incident, service: event.target.value })}>{['checkout-service', 'payment-service', 'order-service', 'auth-service', 'notification-service'].map((service) => <option key={service}>{service}</option>)}</select></label><label className="field-wide">Symptoms<textarea rows={2} value={incident.symptoms} onChange={(event) => setIncident({ ...incident, symptoms: event.target.value })} /></label></div></section>
    {runs ? <div className="evaluation-grid">{runs.map((run) => <article className={`panel evaluation-card ${run.mode}`} key={run.run_id}><div className="evaluation-head"><div><div className="eyebrow">{run.mode === 'with_memory' ? 'HINDSIGHT RECALL ENABLED' : 'RECALL INTENTIONALLY DISABLED'}</div><h2>{run.mode === 'with_memory' ? 'With memory' : 'Without memory'}</h2></div><span className="planner-chip">{run.planner_mode}</span></div><div className="eval-metrics"><div><small>Latency</small><strong>{run.latency_ms} ms</strong></div><div><small>Facts returned</small><strong>{run.relevant_memories_returned}</strong></div><div><small>Failed approach</small><strong>{run.failed_approach_recalled ? 'Recalled' : 'Not recalled'}</strong></div><div><small>Successful approach</small><strong>{run.successful_approach_recalled ? 'Recalled' : 'Not recalled'}</strong></div></div><div className="eval-diagnosis"><small>DIAGNOSIS</small><p>{run.diagnosis}</p><small>RECOMMENDATION</small><p>{run.recommendation}</p></div><div className="run-id">Measured run · {run.run_id.slice(0, 8)}</div></article>)}</div> : <section className="panel eval-empty"><GitBranch size={22} /><strong>No comparison run yet</strong><span>Run both arms against this exact input. Values are measured per run.</span></section>}
  </>
}

function EmptyMessage({ title, text }: { title: string; text: string }) {
  return <div className="empty-block"><span><HardDrive size={18} /></span><strong>{title}</strong><p>{text}</p></div>
}

export default App
