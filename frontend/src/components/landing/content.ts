/**
 * Every word and link on the landing page. Components render this and add no copy of their own, so the page can be
 * reviewed, translated or re-skinned by editing one file. Claims here describe what the system actually does
 * (see the README pipeline): masking happens before classification and drafting, the validation step checks for
 * internal technical detail, HR drafts are always escalated to a person. The brand name is not repeated here; it
 * comes from src/theme/theme.config.ts.
 */

export const nav = {
  links: [
    { label: 'Agents', href: '#agents' },
    { label: 'How it works', href: '#how' },
    { label: 'Human review', href: '#review' },
    { label: 'Privacy', href: '#privacy' },
  ],
  signIn: { label: 'Sign in', href: '/login' },
  getStarted: { label: 'Get started', href: '/register' },
} as const;

export const hero = {
  headline: 'Specialist AI agents that triage and answer your support tickets',
  lead: 'Each ticket is classified, routed to the right specialist and checked before it is sent. Anything that needs a person goes to your team with the draft attached.',
  primary: { label: 'Create an account', href: '/register' },
  secondary: { label: 'Sign in', href: '/login' },
} as const;

export const demo = {
  ariaLabel: 'Example of a ticket being triaged',
  label: 'Example ticket',
  status: 'Agent active',
  customer: 'Customer message',
  ticket: 'I was charged twice for my March invoice. Can someone look at this?',
  classified: 'Classified as',
  labels: [
    { text: 'Billing', tone: 'brand' },
    { text: 'High priority', tone: 'warning' },
    { text: 'Frustrated', tone: 'info' },
  ],
  routed: 'Routed to the billing agent',
  draftLabel: 'Draft reply',
  draft: 'Thanks for flagging this. We are checking your March invoice for a duplicate charge and will confirm the result here.',
  checked: 'Checked before sending: no internal technical detail found',
} as const;

export const agents = {
  id: 'agents',
  title: 'Three specialists, one queue',
  intro: 'Each ticket goes to the agent that knows the subject. Every agent drafts from your knowledge base.',
  items: [
    {
      key: 'technical',
      title: 'Technical agent',
      body: 'Handles product and technical issues. Drafts from your technical documentation and knowledge base.',
      badge: { text: 'Can resolve automatically', tone: 'success' },
    },
    {
      key: 'billing',
      title: 'Billing agent',
      body: 'Handles charges, invoices and plan questions, using your billing policies.',
      badge: { text: 'Can resolve automatically', tone: 'success' },
    },
    {
      key: 'hr',
      title: 'HR agent',
      body: 'Handles people and policy questions. Its draft always goes to a person before it is sent.',
      badge: { text: 'Always reviewed by a person', tone: 'warning' },
    },
  ],
  inputs: {
    title: 'Text, voice or a screenshot',
    body: 'Customers can type, dictate with the microphone or attach a screenshot. Text inside images is read automatically.',
  },
} as const;

export const steps = {
  id: 'how',
  title: 'What happens to a ticket',
  intro: "Five steps, from the customer's message to a reply or a handover.",
  items: [
    { title: 'Submit', body: 'A customer describes the problem by text or voice, with an optional screenshot.' },
    { title: 'Mask', body: 'Names and email addresses are swapped for stand-ins, and phone and card numbers are redacted, before the ticket is classified or drafted.' },
    { title: 'Classify and route', body: 'The ticket gets a category, priority and sentiment, then goes to the technical, billing or HR agent.' },
    { title: 'Draft and check', body: 'The agent drafts a reply from your knowledge base. A validation step checks it for internal technical detail that customers should not see.' },
    { title: 'Send or hand over', body: 'Routine replies go out with the real names and email addresses restored. Critical or low-confidence tickets, and every HR ticket, wait for a person.' },
  ],
} as const;

export const review = {
  id: 'review',
  title: 'People stay in charge of the hard cases',
  intro: "Escalated tickets wait in a review queue with the agent's draft ready to edit.",
  points: [
    "The customer's message and the agent's draft, together.",
    'Edit the draft, then send the reply.',
    'Every HR ticket lands here, along with critical and low-confidence tickets.',
  ],
  mock: {
    label: 'Example review queue',
    queueTitle: 'Needs review',
    rows: [
      { subject: 'Leave balance after a transfer', tag: 'HR', selected: true },
      { subject: 'Refund for a duplicate charge', tag: 'Billing', selected: false },
      { subject: 'Export fails with a timeout', tag: 'Technical', selected: false },
    ],
    draftLabel: 'Draft reply',
    draft: 'Thanks for asking. We are checking your leave balance after the transfer and will confirm the exact figure.',
    actions: ['Send reply'],
  },
} as const;

export const privacy = {
  id: 'privacy',
  title: 'Personal details stay out of the drafting step',
  intro: 'The agents draft from stand-ins and redacted text, not from names and contact details.',
  items: [
    {
      key: 'mask',
      title: 'Masked first',
      body: 'Names and email addresses are swapped for stand-ins, and phone and card numbers are redacted, before classification and drafting.',
    },
    { key: 'restore', title: 'Restored last', body: 'Real names and email addresses are put back into the reply after the agents have finished drafting.' },
    {
      key: 'roles',
      title: 'Access by role',
      body: 'Customers see their own tickets. Agents work the review queue. Admins manage users and see reports.',
    },
  ],
} as const;

export const cta = {
  title: 'Send your first ticket',
  body: 'Create an account and watch a ticket get classified, drafted and checked.',
  primary: { label: 'Create an account', href: '/register' },
  secondary: { label: 'Sign in', href: '/login' },
} as const;

export const footer = {
  links: [
    { label: 'Sign in', href: '/login' },
    { label: 'Create an account', href: '/register' },
  ],
} as const;
