import { writeFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __dir = dirname(fileURLToPath(import.meta.url))
const OUT = join(__dir, '..', 'openapi.json')

const BASE = process.env.API_BASE_URL ?? 'http://localhost:8000'
const URL  = `${BASE}/openapi.json`

console.log(`Fetching ${URL} …`)
const res = await fetch(URL)
if (!res.ok) throw new Error(`HTTP ${res.status} from ${URL}`)

const schema = await res.json()
writeFileSync(OUT, JSON.stringify(schema) + '\n', 'utf8')
console.log(
  `Written → openapi.json  ` +
  `(${Object.keys(schema.paths ?? {}).length} paths, ` +
  `${Object.keys((schema.components ?? {}).schemas ?? {}).length} schemas)`
)
