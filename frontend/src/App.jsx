import { useState } from 'react'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="App" data-testid="app">
      <header className="App-header">
        <h1>🃏 Arkham Assistant</h1>
        <p>AI-powered deckbuilding for Arkham Horror LCG</p>
      </header>
      
      <main>
        <div className="placeholder">
          <h2>Coming Soon</h2>
          <p>Deck builder, card search, and AI chat interface</p>
          <button onClick={() => setCount(count + 1)}>
            Test Button: {count}
          </button>
        </div>
      </main>
    </div>
  )
}

export default App

