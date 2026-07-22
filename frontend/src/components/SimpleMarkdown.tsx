/** Minimal markdown renderer for SKILL.md preview (no external deps). */

type Props = { content: string; className?: string }

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderInline(text: string): string {
  let s = escapeHtml(text)
  s = s.replace(/`([^`]+)`/g, '<code class="md-code">$1</code>')
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  s = s.replace(
    /\[([^\]]+)\]\((https?:[^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer" class="md-link">$1</a>',
  )
  return s
}

function toHtml(src: string): string {
  // Strip YAML frontmatter
  let text = src
  if (text.startsWith('---')) {
    const end = text.indexOf('\n---', 3)
    if (end !== -1) {
      text = text.slice(end + 4).replace(/^\s*\n/, '')
    }
  }

  const lines = text.split(/\r?\n/)
  const out: string[] = []
  let inCode = false
  let codeBuf: string[] = []
  let inList = false

  const closeList = () => {
    if (inList) {
      out.push('</ul>')
      inList = false
    }
  }

  for (const line of lines) {
    if (line.startsWith('```')) {
      if (inCode) {
        out.push(
          `<pre class="md-pre"><code>${escapeHtml(codeBuf.join('\n'))}</code></pre>`,
        )
        codeBuf = []
        inCode = false
      } else {
        closeList()
        inCode = true
      }
      continue
    }
    if (inCode) {
      codeBuf.push(line)
      continue
    }
    if (/^#{1,3}\s+/.test(line)) {
      closeList()
      const level = line.match(/^(#{1,3})/)![1].length
      const body = line.replace(/^#{1,3}\s+/, '')
      out.push(`<h${level} class="md-h${level}">${renderInline(body)}</h${level}>`)
      continue
    }
    if (/^[-*]\s+/.test(line)) {
      if (!inList) {
        out.push('<ul class="md-ul">')
        inList = true
      }
      out.push(`<li>${renderInline(line.replace(/^[-*]\s+/, ''))}</li>`)
      continue
    }
    if (line.trim() === '') {
      closeList()
      continue
    }
    closeList()
    out.push(`<p class="md-p">${renderInline(line)}</p>`)
  }
  closeList()
  if (inCode) {
    out.push(
      `<pre class="md-pre"><code>${escapeHtml(codeBuf.join('\n'))}</code></pre>`,
    )
  }
  return out.join('\n')
}

export function SimpleMarkdown({ content, className }: Props) {
  const html = toHtml(content || '')
  return (
    <div
      className={className ?? 'simple-md'}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
