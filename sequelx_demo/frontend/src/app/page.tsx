'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  Activity,
  BarChart2,
  Database,
  LucideIcon,
  Send,
  Shield,
  X,
  Zap,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

type SelectorType = 'rfq' | 'order' | 'contract' | 'supplier' | null;

interface AgentTab {
  id: string;
  label: string;
  icon: LucideIcon;
  active: boolean;
  title: string;
  subtitle: string;
  selectorType: SelectorType;
  selectorPlaceholder: string;
  actionLabel: string;
  loadingLabel: string;
  emptyStateTitle: string;
  emptyStateHint: string;
  inputPlaceholder: string;
}

const TABS: AgentTab[] = [
  {
    id: 'bid_intelligence',
    label: 'Bid Intelligence',
    icon: Activity,
    active: true,
    title: 'Bid Intelligence',
    subtitle: 'Award Strategy - TCO Analysis - Multi-Criteria Scoring',
    selectorType: 'rfq',
    selectorPlaceholder: 'Select an RFQ event...',
    actionLabel: 'Analyze Bids',
    loadingLabel: 'Running bid analysis...',
    emptyStateTitle: 'Select an RFQ from the dropdown and click Analyze Bids',
    emptyStateHint: 'Or ask a sourcing question below',
    inputPlaceholder: 'Ask a follow-up sourcing question...',
  },
  {
    id: 'invoice_intelligence',
    label: 'Invoice Intelligence',
    icon: Database,
    active: true,
    title: 'Invoice Intelligence',
    subtitle: 'AP Exceptions | STP | Workflow',
    selectorType: 'order',
    selectorPlaceholder: 'Select an order for invoice investigation...',
    actionLabel: 'Investigate Invoice',
    loadingLabel: 'Running invoice control-tower analysis...',
    emptyStateTitle: 'Select an order',
    emptyStateHint: 'Run investigation',
    inputPlaceholder: 'Ask an invoice or workflow question...',
  },
  {
    id: 'contract_intelligence',
    label: 'Contract Intelligence',
    icon: Zap,
    active: true,
    title: 'Contract Intelligence',
    subtitle: 'Renewals | Clauses | Obligations',
    selectorType: 'contract',
    selectorPlaceholder: 'Select a contract...',
    actionLabel: 'Review Contract',
    loadingLabel: 'Running contract analysis...',
    emptyStateTitle: 'Select a contract',
    emptyStateHint: 'Review contract',
    inputPlaceholder: 'Ask a contract or renewal question...',
  },
  {
    id: 'supplier_dna',
    label: 'Supplier DNA',
    icon: Shield,
    active: true,
    title: 'Supplier DNA',
    subtitle: 'Trust | Compliance | Verification',
    selectorType: 'supplier',
    selectorPlaceholder: 'Select a supplier...',
    actionLabel: 'Assess Supplier',
    loadingLabel: 'Running supplier analysis...',
    emptyStateTitle: 'Select a supplier',
    emptyStateHint: 'Assess supplier',
    inputPlaceholder: 'Ask a supplier trust or compliance question...',
  },
  {
    id: 'procurement_insights',
    label: 'Procurement Insights',
    icon: BarChart2,
    active: true,
    title: 'Procurement Insights',
    subtitle: 'Portfolio Signals | Flow Pressure | Risk Concentration',
    selectorType: null,
    selectorPlaceholder: '',
    actionLabel: 'Run Brief',
    loadingLabel: 'Running executive synthesis...',
    emptyStateTitle: 'Run a portfolio brief',
    emptyStateHint: 'Ask for pressure points, supplier concentration, or action plan',
    inputPlaceholder: 'Ask a portfolio, spend, or risk question...',
  },
];

interface TraceEntry {
  source: string;
  eventId: string;
  dataPreview: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  trace?: TraceEntry[];
}

interface RfqOption {
  eventId: string;
  title: string;
  status: string;
  category: string;
  bidCount: number;
}

interface OrderOption {
  orderId: string;
  poStatus: string;
  asnStatus: string;
  paymentStatus: string;
  invoiceStatus: string;
  grnStatus: string;
  lineItemsCount: number;
}

interface ContractOption {
  contractId: string;
  documentId: string | null;
  status: string;
  contractType: string | null;
  contractValue: string | number | null;
  currency: string | null;
  startDate: string | null;
  endDate: string | null;
  clausesCount: number;
}

interface SupplierOption {
  orgId: string;
  organisationName: string;
  organisationType: string;
  status: string;
  createdAt: string | null;
  country: string | null;
  city: string | null;
}

interface InsightsKpiBucket {
  totalSpend?: number;
  orderCount?: number;
  avgOrderValue?: number;
  completionRate?: number;
  completedOrders?: number;
  totalRfqs?: number;
  avgBidsPerRfq?: number;
  activeContracts?: number;
  expiringSoon?: number;
  suppliersWithGaps?: number;
  criticalGaps?: number;
}

interface InsightsOverview {
  kpis?: {
    spend?: InsightsKpiBucket;
    pipeline?: InsightsKpiBucket;
    rfq?: InsightsKpiBucket;
    contracts?: InsightsKpiBucket;
    compliance?: InsightsKpiBucket;
  };
  spendAnalysis?: {
    totalSpend?: number;
    totalOrders?: number;
    avgOrderValue?: number;
    spendByCategory?: Array<{ category: string; amount: number }>;
    topSuppliers?: Array<{ supplier: string; spend: number }>;
  };
  pipelineStatus?: {
    totalOrders?: number;
    completedOrders?: number;
    completionRate?: number;
  };
  rfqPerformance?: {
    totalRfqs?: number;
    totalBids?: number;
    avgBidsPerRfq?: number;
    rfqStatusBreakdown?: Record<string, number>;
    topCategories?: Array<[string, number]>;
  };
  contractHealth?: {
    totalContracts?: number;
    activeContracts?: number;
    expiredContracts?: number;
    expiringIn30Days?: number;
    overdueObligations?: number;
  };
  complianceGaps?: {
    totalSuppliers?: number;
    suppliersWithGaps?: number;
    criticalGaps?: number;
    moderateGaps?: number;
    gapDetails?: Array<{
      orgId: string;
      name: string;
      gapScore: number;
      issues: string[];
      complianceCount: number;
      certificateCount: number;
    }>;
  };
}

type AnalysisOption = RfqOption | OrderOption | ContractOption | SupplierOption;

function isRfqOption(option: AnalysisOption): option is RfqOption {
  return 'eventId' in option;
}

function isContractOption(option: AnalysisOption): option is ContractOption {
  return 'contractId' in option;
}

function isOrderOption(option: AnalysisOption): option is OrderOption {
  return 'orderId' in option;
}

function isSupplierOption(option: AnalysisOption): option is SupplierOption {
  return 'orgId' in option;
}

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: value >= 1000 ? 1 : 0,
  }).format(value || 0);
}

export default function Home() {
  const [activeTab, setActiveTab] = useState('bid_intelligence');
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [analysisOptions, setAnalysisOptions] = useState<AnalysisOption[]>([]);
  const [selectedEntity, setSelectedEntity] = useState('');
  const [traceVisible, setTraceVisible] = useState<Record<number, boolean>>({});
  const [fetchError, setFetchError] = useState(false);
  const [insightsOverview, setInsightsOverview] = useState<InsightsOverview | null>(null);
  const [insightsError, setInsightsError] = useState(false);
  const [chatOverlayOpen, setChatOverlayOpen] = useState(false);
  const outputRef = useRef<HTMLDivElement>(null);

  const activeTabConfig = TABS.find((tab) => tab.id === activeTab) ?? TABS[0];
  const invoiceOptions = analysisOptions.filter((option): option is OrderOption => isOrderOption(option));
  const contractOptions = analysisOptions.filter((option): option is ContractOption => isContractOption(option));
  const supplierOptions = analysisOptions.filter((option): option is SupplierOption => isSupplierOption(option));
  const invoiceApprovedCount = invoiceOptions.filter(
    (order) => order.invoiceStatus?.toLowerCase() === 'approved',
  ).length;
  const paymentPendingCount = invoiceOptions.filter(
    (order) => order.paymentStatus?.toLowerCase() === 'pending',
  ).length;
  const blockedWorkflowCount = invoiceOptions.filter((order) =>
    [order.poStatus, order.asnStatus, order.paymentStatus, order.invoiceStatus, order.grnStatus]
      .some((status) => ['pending', 'rejected'].includes((status || '').toLowerCase())),
  ).length;
  const invoiceClearCount = Math.max(invoiceOptions.length - blockedWorkflowCount, 0);
  const contractReviewCount = contractOptions.filter(
    (contract) => (contract.status || '').toLowerCase().includes('review'),
  ).length;
  const contractDraftCount = contractOptions.filter(
    (contract) => (contract.status || '').toLowerCase().includes('draft'),
  ).length;
  const contractClauseGapCount = contractOptions.filter(
    (contract) => (contract.clausesCount || 0) === 0,
  ).length;
  const contractLiveCount = Math.max(contractOptions.length - contractDraftCount, 0);
  const supplierPendingCount = supplierOptions.filter(
    (supplier) => (supplier.status || '').toLowerCase() === 'pending',
  ).length;
  const supplierProfileGapCount = supplierOptions.filter(
    (supplier) => !supplier.country || !supplier.city,
  ).length;
  const supplierNamedCount = supplierOptions.filter(
    (supplier) => !supplier.organisationName.startsWith('Supplier-'),
  ).length;
  const supplierApprovedCount = supplierOptions.filter(
    (supplier) => (supplier.status || '').toLowerCase() === 'approved',
  ).length;
  const supplierCompleteCount = Math.max(supplierOptions.length - supplierProfileGapCount, 0);
  const insightsSpend = insightsOverview?.spendAnalysis;
  const insightsPipeline = insightsOverview?.pipelineStatus;
  const insightsRfq = insightsOverview?.rfqPerformance;
  const insightsContracts = insightsOverview?.contractHealth;
  const insightsCompliance = insightsOverview?.complianceGaps;
  const insightsTopCategories = insightsSpend?.spendByCategory ?? [];
  const insightsTopSuppliers = insightsSpend?.topSuppliers ?? [];
  const insightsGapDetails = insightsCompliance?.gapDetails ?? [];

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  useEffect(() => {
    if (!chatOverlayOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setChatOverlayOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [chatOverlayOpen]);

  useEffect(() => {
    setSelectedEntity('');
    setFetchError(false);
    setAnalysisOptions([]);

    const selectorType = activeTabConfig.selectorType;
    if (!selectorType) {
      setAnalysisOptions([]);
      return;
    }

    const endpoint =
      selectorType === 'rfq' ? '/api/rfqs' :
      selectorType === 'order' ? '/api/orders' :
      selectorType === 'contract' ? '/api/contracts' :
      '/api/suppliers';
    fetch(`${API_BASE_URL}${endpoint}`)
      .then((response) => response.json())
      .then((data) => {
        if (Array.isArray(data.data)) {
          setAnalysisOptions(data.data);
          setFetchError(false);
        } else {
          setAnalysisOptions([]);
          setFetchError(true);
        }
      })
      .catch((error) => {
        console.error(`Failed to fetch ${selectorType} data:`, error);
        setAnalysisOptions([]);
        setFetchError(true);
      });
  }, [activeTabConfig]);

  useEffect(() => {
    if (activeTab !== 'procurement_insights') {
      return;
    }

    setInsightsError(false);
    fetch(`${API_BASE_URL}/api/insights`)
      .then((response) => response.json())
      .then((data) => {
        if (data?.data && typeof data.data === 'object') {
          setInsightsOverview(data.data as InsightsOverview);
          setInsightsError(false);
        } else {
          setInsightsOverview(null);
          setInsightsError(true);
        }
      })
      .catch((error) => {
        console.error('Failed to fetch insights data:', error);
        setInsightsOverview(null);
        setInsightsError(true);
      });
  }, [activeTab]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading || !activeTabConfig.active) return;

    const userMsg: Message = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setChatOverlayOpen(true);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          tabId: activeTab,
          history: messages.map((message) => ({ role: message.role, content: message.content })),
        }),
      });

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.response || data.error || 'No response',
          trace: data.trace,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Cannot connect to backend. Make sure the API is running on port 8000.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnalyze = () => {
    if (!selectedEntity) return;

    if (activeTab === 'bid_intelligence') {
      const rfq = analysisOptions.find(
        (option): option is RfqOption => isRfqOption(option) && option.eventId === selectedEntity,
      );

      if (rfq && rfq.bidCount === 0) {
        setChatOverlayOpen(true);
        setMessages((prev) => [
          ...prev,
          { role: 'user', content: `Analyze bids for ${selectedEntity}` },
          {
            role: 'assistant',
            content: `No bids have been submitted for this event yet (${rfq.title}). Select an event with active bids to run the analysis.`,
          },
        ]);
        return;
      }

      const prompt = `Analyze all bids for event ${selectedEntity}${rfq ? ` - ${rfq.title}` : ''}. Provide TCO comparison, scoring breakdown, winner recommendation with reasoning, and risk flags.`;
      sendMessage(prompt);
      return;
    }

    if (activeTab === 'invoice_intelligence') {
      const order = analysisOptions.find(
        (option): option is OrderOption => !isRfqOption(option) && option.orderId === selectedEntity,
      );

      const prompt = `Investigate invoice flow for order ${selectedEntity}. Produce an exception-first brief covering workflow status, anomalies, STP score, blockers, and the exact next action.${order ? ` Current states: PO ${order.poStatus}, ASN ${order.asnStatus}, Invoice ${order.invoiceStatus}, GRN ${order.grnStatus}, Payment ${order.paymentStatus}.` : ''}`;
      sendMessage(prompt);
      return;
    }

    if (activeTab === 'contract_intelligence') {
      const contract = analysisOptions.find(
        (option): option is ContractOption => isContractOption(option) && option.contractId === selectedEntity,
      );

      const contractLabel = contract?.documentId || contract?.contractId || selectedEntity;
      const prompt =
        `Open a legal-risk dossier for contract ${contractLabel}. ` +
        `Assess lifecycle status, risk score drivers, clause coverage, obligation exposure, and the exact next action. ` +
        (contract
          ? `Current portfolio facts: status ${contract.status}, type ${contract.contractType}, clauses ${contract.clausesCount}, value ${contract.contractValue} ${contract.currency || ''}.`
          : '');
      sendMessage(prompt);
      return;
    }

    if (activeTab === 'supplier_dna') {
      const supplier = analysisOptions.find(
        (option): option is SupplierOption => isSupplierOption(option) && option.orgId === selectedEntity,
      );

      const supplierLabel = supplier?.organisationName || selectedEntity;
      const prompt =
        `Decode supplier DNA for ${supplierLabel} (${selectedEntity}). ` +
        `Assess trust score drivers, compliance posture, certification strength, profile completeness, and the exact next action. ` +
        (supplier
          ? `Current profile facts: status ${supplier.status}, type ${supplier.organisationType}, location ${supplier.city || 'unknown city'}, ${supplier.country || 'unknown country'}.`
          : '');
      sendMessage(prompt);
      return;
    }

    if (activeTab === 'procurement_insights') {
      sendMessage(
        'Create an executive procurement brief covering spend signals, pipeline friction, sourcing competition, contract exposure, supplier gaps, and the top three leadership actions.',
      );
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    sendMessage(input);
    setInput('');
  };

  const renderOptionLabel = (option: AnalysisOption) => {
    if (isRfqOption(option)) {
      return `${option.eventId} - ${option.title || 'Untitled'} - ${option.category} - ${option.status} - ${option.bidCount} bid${option.bidCount !== 1 ? 's' : ''}`;
    }

    if (isContractOption(option)) {
      const label = option.documentId || option.contractId;
      return `${label} - ${option.contractType || 'Unknown type'} - ${option.status} - ${option.clausesCount} clause${option.clausesCount !== 1 ? 's' : ''}`;
    }

    if (isSupplierOption(option)) {
      return `${option.organisationName} - ${option.status} - ${option.organisationType} - ${option.city || 'Unknown city'}${option.country ? `, ${option.country}` : ''}`;
    }

    return `${option.orderId} - invoice ${option.invoiceStatus} - payment ${option.paymentStatus} - po ${option.poStatus} - ${option.lineItemsCount} line item${option.lineItemsCount !== 1 ? 's' : ''}`;
  };

  const getOptionValue = (option: AnalysisOption) => {
    if (isRfqOption(option)) return option.eventId;
    if (isContractOption(option)) return option.contractId;
    if (isSupplierOption(option)) return option.orgId;
    return option.orderId;
  };

  const getOptionKey = (option: AnalysisOption, index: number) => {
    if (isRfqOption(option)) return `rfq-${option.eventId || index}`;
    if (isContractOption(option)) return `contract-${option.contractId || option.documentId || index}`;
    if (isSupplierOption(option)) return `supplier-${option.orgId || index}`;
    return `order-${option.orderId || index}`;
  };

  const resetConversationForTab = (tabId: string) => {
    setActiveTab(tabId);
    setMessages([]);
    setTraceVisible({});
    setInput('');
    setChatOverlayOpen(false);
  };

  return (
    <div className="app">
      <div className={`workspace-shell ${chatOverlayOpen ? 'chat-open' : ''}`}>
      <div className="sidebar">
        <div className="sidebar-logo">
          <h1>Sequel<span>X</span></h1>
        </div>

        <div className="sidebar-section-label">Agents</div>
        <div className="sidebar-nav">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={`nav-btn ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => {
                  if (tab.active) {
                    resetConversationForTab(tab.id);
                  }
                }}
                style={!tab.active ? { opacity: 0.4, cursor: 'default' } : {}}
              >
                <Icon size={15} />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="sidebar-footer">
          <span className="status-dot"></span>Engine Live
        </div>
      </div>

      <div className={`main ${activeTab === 'invoice_intelligence' ? 'invoice-main' : activeTab === 'supplier_dna' ? 'supplier-main' : activeTab === 'procurement_insights' ? 'insights-main' : ''}`}>
        <div className={`header ${activeTab === 'invoice_intelligence' ? 'invoice-header' : activeTab === 'contract_intelligence' ? 'contract-header' : activeTab === 'supplier_dna' ? 'supplier-header' : activeTab === 'procurement_insights' ? 'insights-header' : ''}`}>
          <div className="header-left">
            {activeTab === 'invoice_intelligence' && (
              <div className="invoice-eyebrow">AP CONTROL TOWER</div>
            )}
            {activeTab === 'contract_intelligence' && (
              <div className="contract-eyebrow">LEGAL RISK DESK</div>
            )}
            {activeTab === 'supplier_dna' && (
              <div className="supplier-eyebrow">SUPPLIER GENOME LAB</div>
            )}
            {activeTab === 'procurement_insights' && (
              <div className="insights-tab-eyebrow">EXECUTIVE MARKET VIEW</div>
            )}
            <h2>{activeTabConfig.title}</h2>
            <p>{activeTabConfig.subtitle}</p>
          </div>
          <div className="header-right">
            {messages.length > 0 && !chatOverlayOpen && (
              <button
                className="workspace-open-btn"
                onClick={() => setChatOverlayOpen(true)}
              >
                Open Workspace
              </button>
            )}
            <span
              className="status-dot"
              style={{
                display: 'inline-block',
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: '#00a854',
              }}
            ></span>
            Live
          </div>
        </div>

        {activeTab === 'invoice_intelligence' && (
          <div className="invoice-command-center">
            <div className="invoice-ops-shell">
              <div className="invoice-hero-card">
                <div className="invoice-hero-top">
                  <span className="invoice-panel-label">Queue Focus</span>
                  <span className="invoice-hero-badge">{invoiceClearCount} clear</span>
                </div>
                <strong className="invoice-hero-value">{selectedEntity || 'No Order Selected'}</strong>
                <div className="invoice-hero-grid">
                  <div className="invoice-hero-cell">
                    <span>Approved</span>
                    <strong>{invoiceApprovedCount}</strong>
                  </div>
                  <div className="invoice-hero-cell warn">
                    <span>Pending</span>
                    <strong>{paymentPendingCount}</strong>
                  </div>
                  <div className="invoice-hero-cell alert">
                    <span>Blocked</span>
                    <strong>{blockedWorkflowCount}</strong>
                  </div>
                </div>
              </div>

              <div className="invoice-lane-stack">
                <div className="invoice-lane-card">
                  <span>Orders</span>
                  <strong>{invoiceOptions.length}</strong>
                </div>
                <div className="invoice-lane-card amber">
                  <span>Approved</span>
                  <strong>{invoiceApprovedCount}</strong>
                </div>
                <div className="invoice-lane-card red">
                  <span>Payment Hold</span>
                  <strong>{paymentPendingCount}</strong>
                </div>
                <div className="invoice-lane-card teal">
                  <span>Workflow Hold</span>
                  <strong>{blockedWorkflowCount}</strong>
                </div>
              </div>

              <div className="invoice-action-strip">
                <select
                  value={selectedEntity}
                  onChange={(event) => setSelectedEntity(event.target.value)}
                  disabled={fetchError}
                >
                  <option value="">
                    {fetchError
                      ? 'Error loading data'
                      : activeTabConfig.selectorPlaceholder}
                  </option>
                  {analysisOptions.map((option, index) => {
                    const value = getOptionValue(option);
                    return (
                      <option key={getOptionKey(option, index)} value={value}>
                        {renderOptionLabel(option)}
                      </option>
                    );
                  })}
                </select>
                <button
                  className="analyze-btn invoice-analyze-btn"
                  onClick={handleAnalyze}
                  disabled={!selectedEntity || isLoading || !activeTabConfig.active}
                >
                  {isLoading ? 'Analyzing...' : activeTabConfig.actionLabel}
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'contract_intelligence' && (
          <div className="contract-command-center">
            <div className="contract-review-desk">
              <div className="contract-review-card">
                <div className="contract-review-head">
                  <span className="contract-panel-label">Matter</span>
                  <span className="contract-review-badge">{contractLiveCount} active</span>
                </div>
                <strong className="contract-review-value">{selectedEntity || 'No Contract Selected'}</strong>
                <div className="contract-review-controls">
                  <select
                    value={selectedEntity}
                    onChange={(event) => setSelectedEntity(event.target.value)}
                    disabled={fetchError}
                  >
                    <option value="">
                      {fetchError
                        ? 'Error loading data'
                        : activeTabConfig.selectorPlaceholder}
                    </option>
                    {analysisOptions.map((option, index) => {
                      const value = getOptionValue(option);
                      return (
                        <option key={getOptionKey(option, index)} value={value}>
                          {renderOptionLabel(option)}
                        </option>
                      );
                    })}
                  </select>
                  <button
                    className="analyze-btn contract-analyze-btn"
                    onClick={handleAnalyze}
                    disabled={!selectedEntity || isLoading || !activeTabConfig.active}
                  >
                    {isLoading ? 'Analyzing...' : activeTabConfig.actionLabel}
                  </button>
                </div>
              </div>

              <div className="contract-risk-column">
                <div className="contract-risk-band review">
                  <span>Review</span>
                  <strong>{contractReviewCount}</strong>
                </div>
                <div className="contract-risk-band draft">
                  <span>Draft</span>
                  <strong>{contractDraftCount}</strong>
                </div>
                <div className="contract-risk-band gap">
                  <span>Clause Gaps</span>
                  <strong>{contractClauseGapCount}</strong>
                </div>
              </div>

              <div className="contract-snapshot-grid">
                <div className="contract-snapshot-card">
                  <span>Portfolio</span>
                  <strong>{contractOptions.length}</strong>
                </div>
                <div className="contract-snapshot-card review">
                  <span>In Review</span>
                  <strong>{contractReviewCount}</strong>
                </div>
                <div className="contract-snapshot-card draft">
                  <span>Draft Risk</span>
                  <strong>{contractDraftCount}</strong>
                </div>
                <div className="contract-snapshot-card gap">
                  <span>Active</span>
                  <strong>{contractLiveCount}</strong>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'supplier_dna' && (
          <div className="supplier-command-center">
            <div className="supplier-lab-grid">
              <div className="supplier-signal-stack">
                <div className="supplier-signal-card primary">
                  <span>Suppliers</span>
                  <strong>{supplierOptions.length}</strong>
                </div>
                <div className="supplier-signal-card approved">
                  <span>Approved</span>
                  <strong>{supplierApprovedCount}</strong>
                </div>
                <div className="supplier-signal-card pending">
                  <span>Pending</span>
                  <strong>{supplierPendingCount}</strong>
                </div>
                <div className="supplier-signal-card gaps">
                  <span>Gaps</span>
                  <strong>{supplierProfileGapCount}</strong>
                </div>
              </div>

              <div className="supplier-profile-stage">
                <div className="supplier-stage-head">
                  <div className="supplier-stage-copy">
                    <span className="supplier-panel-label">Supplier</span>
                    <strong className="supplier-stage-value">{selectedEntity || 'No Supplier Selected'}</strong>
                  </div>
                  <div className="supplier-chip-cloud">
                    <span>{supplierNamedCount} named</span>
                    <span>{supplierCompleteCount} complete</span>
                    <span>{supplierApprovedCount} approved</span>
                  </div>
                </div>

                <div className="supplier-stage-controls">
                  <select
                    value={selectedEntity}
                    onChange={(event) => setSelectedEntity(event.target.value)}
                    disabled={fetchError}
                  >
                    <option value="">
                      {fetchError
                        ? 'Error loading data'
                        : activeTabConfig.selectorPlaceholder}
                    </option>
                    {analysisOptions.map((option, index) => {
                      const value = getOptionValue(option);
                      return (
                        <option key={getOptionKey(option, index)} value={value}>
                          {renderOptionLabel(option)}
                        </option>
                      );
                    })}
                  </select>
                  <button
                    className="analyze-btn supplier-analyze-btn"
                    onClick={handleAnalyze}
                    disabled={!selectedEntity || isLoading || !activeTabConfig.active}
                  >
                    {isLoading ? 'Analyzing...' : activeTabConfig.actionLabel}
                  </button>
                </div>

                <div className="supplier-matrix">
                  <div className="supplier-matrix-card">
                    <span>Named</span>
                    <strong>{supplierNamedCount}</strong>
                  </div>
                  <div className="supplier-matrix-card good">
                    <span>Complete</span>
                    <strong>{supplierCompleteCount}</strong>
                  </div>
                  <div className="supplier-matrix-card caution">
                    <span>Pending</span>
                    <strong>{supplierPendingCount}</strong>
                  </div>
                  <div className="supplier-matrix-card muted">
                    <span>Incomplete</span>
                    <strong>{supplierProfileGapCount}</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'procurement_insights' && (
          <div className="insights-command-center">
            <div className="insights-cockpit">
              <div className="insights-hero-board">
                <div className="insights-hero-head">
                  <div>
                    <span className="insights-eyebrow">Executive Cockpit</span>
                    <strong className="insights-hero-value">
                      {formatCompactNumber(insightsSpend?.totalSpend ?? 0)}
                    </strong>
                  </div>
                  <div className="insights-hero-meta">
                    <span>{formatCompactNumber(insightsSpend?.totalOrders ?? 0)} orders</span>
                    <span>{Math.round(insightsPipeline?.completionRate ?? 0)}% completion</span>
                  </div>
                </div>

                <div className="insights-hero-grid">
                  <div className="insights-hero-cell">
                    <span>RFQs</span>
                    <strong>{formatCompactNumber(insightsRfq?.totalRfqs ?? 0)}</strong>
                  </div>
                  <div className="insights-hero-cell">
                    <span>Bids / RFQ</span>
                    <strong>{(insightsRfq?.avgBidsPerRfq ?? 0).toFixed(1)}</strong>
                  </div>
                  <div className="insights-hero-cell">
                    <span>Contracts</span>
                    <strong>{formatCompactNumber(insightsContracts?.totalContracts ?? 0)}</strong>
                  </div>
                  <div className="insights-hero-cell alert">
                    <span>Critical Gaps</span>
                    <strong>{formatCompactNumber(insightsCompliance?.criticalGaps ?? 0)}</strong>
                  </div>
                </div>
              </div>

              <div className="insights-pulse-rail">
                <div className="insights-pulse-card">
                  <span>Pipeline</span>
                  <strong>{Math.round(insightsPipeline?.completionRate ?? 0)}%</strong>
                  <small>{formatCompactNumber(insightsPipeline?.completedOrders ?? 0)} cleared</small>
                </div>
                <div className="insights-pulse-card contract">
                  <span>Expiring</span>
                  <strong>{formatCompactNumber(insightsContracts?.expiringIn30Days ?? 0)}</strong>
                  <small>30-day window</small>
                </div>
                <div className="insights-pulse-card supplier">
                  <span>Supplier Gaps</span>
                  <strong>{formatCompactNumber(insightsCompliance?.suppliersWithGaps ?? 0)}</strong>
                  <small>network pressure</small>
                </div>
              </div>

              <div className="insights-action-deck">
                <button
                  className="insights-action-btn primary"
                  disabled={isLoading || insightsError}
                  onClick={() => sendMessage('Give me the executive procurement brief for this portfolio right now.')}
                >
                  Executive Brief
                </button>
                <button
                  className="insights-action-btn"
                  disabled={isLoading || insightsError}
                  onClick={() => sendMessage('Surface the biggest procurement pressure points and risk clusters across pipeline, contracts, and suppliers.')}
                >
                  Pressure Points
                </button>
                <button
                  className="insights-action-btn"
                  disabled={isLoading || insightsError}
                  onClick={() => sendMessage('Give me a leadership action plan for the next 30 days across sourcing, AP flow, contracts, and supplier risk.')}
                >
                  30-Day Actions
                </button>
              </div>

              <div className="insights-market-grid">
                <div className="insights-panel">
                  <div className="insights-panel-head">
                    <span>Category Heat</span>
                    <strong>Top spend concentration</strong>
                  </div>
                  <div className="insights-list">
                    {insightsTopCategories.slice(0, 4).map((item) => (
                      <div key={item.category} className="insights-row">
                        <span>{item.category}</span>
                        <strong>{formatCompactNumber(item.amount ?? 0)}</strong>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="insights-panel">
                  <div className="insights-panel-head">
                    <span>Supplier Concentration</span>
                    <strong>Top exposure</strong>
                  </div>
                  <div className="insights-list">
                    {insightsTopSuppliers.slice(0, 4).map((item) => (
                      <div key={item.supplier} className="insights-row">
                        <span>{item.supplier}</span>
                        <strong>{formatCompactNumber(item.spend ?? 0)}</strong>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="insights-panel watchlist">
                  <div className="insights-panel-head">
                    <span>Risk Watchlist</span>
                    <strong>Gap names</strong>
                  </div>
                  <div className="insights-list">
                    {insightsGapDetails.slice(0, 4).map((item) => (
                      <div key={item.orgId} className="insights-row">
                        <span>{item.name}</span>
                        <strong>{item.gapScore}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTabConfig.selectorType && activeTab !== 'invoice_intelligence' && activeTab !== 'contract_intelligence' && activeTab !== 'supplier_dna' && (
          <div className="selector-bar">
            <select
              value={selectedEntity}
              onChange={(event) => setSelectedEntity(event.target.value)}
              disabled={fetchError}
            >
                  <option value="">
                    {fetchError
                  ? 'Error loading data'
                      : activeTabConfig.selectorPlaceholder}
                  </option>
                {analysisOptions.map((option, index) => {
                const value = getOptionValue(option);
                return (
                  <option key={getOptionKey(option, index)} value={value}>
                    {renderOptionLabel(option)}
                  </option>
                );
              })}
            </select>
            <button
              className="analyze-btn"
              onClick={handleAnalyze}
              disabled={!selectedEntity || isLoading || !activeTabConfig.active}
            >
              {isLoading ? 'Analyzing...' : activeTabConfig.actionLabel}
            </button>
          </div>
        )}
      </div>
      </div>

      {chatOverlayOpen && (
        <div className="chat-overlay" onClick={() => setChatOverlayOpen(false)}>
          <div className="chat-overlay-panel" onClick={(event) => event.stopPropagation()}>
            <div className="chat-overlay-header">
              <div>
                <span className="chat-overlay-label">{activeTabConfig.title}</span>
                <strong className="chat-overlay-title">Analysis Workspace</strong>
              </div>
              <button
                className="chat-overlay-close"
                onClick={() => setChatOverlayOpen(false)}
                aria-label="Close analysis workspace"
              >
                <X size={18} />
              </button>
            </div>

            <div
              className={`output-area chat-overlay-body ${activeTab === 'invoice_intelligence' ? 'invoice-output-area' : activeTab === 'procurement_insights' ? 'insights-output-area' : ''}`}
              ref={outputRef}
            >
              {messages.length === 0 && (
                <div
                  className={
                    activeTab === 'invoice_intelligence'
                      ? 'invoice-empty-state'
                      : activeTab === 'contract_intelligence'
                        ? 'contract-empty-state'
                        : activeTab === 'supplier_dna'
                          ? 'supplier-empty-state'
                          : activeTab === 'procurement_insights'
                            ? 'insights-empty-state'
                          : ''
                  }
                  style={{ textAlign: 'center', padding: '80px 20px', color: '#bbb' }}
                >
                  {activeTab === 'invoice_intelligence' && (
                    <div className="invoice-empty-banner">Queue Live</div>
                  )}
                  {activeTab === 'contract_intelligence' && (
                    <div className="contract-empty-banner">Portfolio Live</div>
                  )}
                  {activeTab === 'supplier_dna' && (
                    <div className="supplier-empty-banner">Network Live</div>
                  )}
                  {activeTab === 'procurement_insights' && (
                    <div className="insights-empty-banner">Board View</div>
                  )}
                  <Activity size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
                  <p style={{ fontSize: '0.9rem' }}>
                    {activeTabConfig.emptyStateTitle}
                  </p>
                  <p style={{ fontSize: '0.78rem', marginTop: 6 }}>
                    {activeTabConfig.emptyStateHint}
                  </p>
                </div>
              )}

              {messages.map((msg, idx) => (
                <div key={idx}>
                  {msg.role === 'user' ? (
                    <div className={`user-message ${activeTab === 'invoice_intelligence' ? 'invoice-user-message' : activeTab === 'contract_intelligence' ? 'contract-user-message' : activeTab === 'supplier_dna' ? 'supplier-user-message' : activeTab === 'procurement_insights' ? 'insights-user-message' : ''}`}>{msg.content}</div>
                  ) : (
                    <div className={`ai-message ${activeTab === 'invoice_intelligence' ? 'invoice-ai-message' : activeTab === 'contract_intelligence' ? 'contract-ai-message' : activeTab === 'supplier_dna' ? 'supplier-ai-message' : activeTab === 'procurement_insights' ? 'insights-ai-message' : ''}`}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>

                      {msg.trace && msg.trace.length > 0 && (
                        <>
                          <button
                            className="trace-btn"
                            onClick={() => setTraceVisible((prev) => ({ ...prev, [idx]: !prev[idx] }))}
                          >
                            {traceVisible[idx] ? 'Hide' : 'Show'} data source
                          </button>
                          {traceVisible[idx] && (
                            <div className="trace-panel">
                              {msg.trace.map((trace, traceIndex) => (
                                <div key={traceIndex}>
                                  Source: {trace.source}
                                  {'\n'}
                                  Entity: {trace.eventId}
                                  {'\n'}
                                  Preview: {trace.dataPreview}
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {isLoading && (
                <div className="loading-indicator">
                  <div className="loading-dot"></div>
                  {activeTabConfig.loadingLabel}
                </div>
              )}
            </div>

            <form className="input-bar chat-overlay-footer" onSubmit={handleSubmit}>
              <input
                type="text"
                placeholder={activeTabConfig.inputPlaceholder}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                disabled={isLoading || !activeTabConfig.active}
              />
              <button
                type="submit"
                className="send-btn"
                disabled={isLoading || !input.trim() || !activeTabConfig.active}
              >
                <Send size={16} />
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
