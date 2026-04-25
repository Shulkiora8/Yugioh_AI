import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Send, Plus, Trash2, Save, Search, Book, Swords, X, Info,
  LayoutGrid, List, Edit2, Copy, ArrowLeft, LogOut
} from 'lucide-react';
import Login from './Login';

const API_URL = 'http://localhost:8000';

function App() {
  // Auth State
  const [token, setToken] = useState(localStorage.getItem('token') || null);
  const [user, setUser] = useState(null);

  // Navigation State
  const [view, setView] = useState('dashboard'); // 'dashboard' | 'editor'

  // Dashboard State
  const [savedDecks, setSavedDecks] = useState([]);
  const [dashboardSearch, setDashboardSearch] = useState('');
  const [viewMode, setViewMode] = useState('grid');

  // Editor State
  const [activeTab, setActiveTab] = useState('rules');
  const [dbSearchTerm, setDbSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState('All');
  const [displayLimit, setDisplayLimit] = useState(100);
  const [selectedCard, setSelectedCard] = useState(null);
  const [messages, setMessages] = useState({
    rules: [{ text: "¡Hola! Soy tu asistente de reglas.", type: 'ai' }],
    decks: [{ text: "Dime qué mazo quieres construir.", type: 'ai' }]
  });
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [dbResults, setDbResults] = useState([]);
  const [deck, setDeck] = useState({ name: 'Nuevo Mazo', main: [], extra: [], side: [] });

  const editorRef = useRef(null);

  // Chat & UI State
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatPos, setChatPos] = useState({ x: 100, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const getRightEdgeOfEditor = () => {
    const rightSidebarW = Math.min(340, Math.max(240, window.innerWidth * 0.22));
    return window.innerWidth - rightSidebarW - 75;
  };
  const [togglePos, setTogglePos] = useState({ x: getRightEdgeOfEditor(), y: window.innerHeight - 80 });
  const [isToggleDragging, setIsToggleDragging] = useState(false);
  const [toggleDragOffset, setToggleDragOffset] = useState({ x: 0, y: 0 });
  const toggleDidMove = useRef(false);

  // --- Effects ---

  useEffect(() => {
    // 1. Initial State for history
    if (!window.history.state) {
      window.history.replaceState({ view: 'dashboard' }, '');
    }

    // 2. Handle Browser Back/Forward
    const handlePopState = (e) => {
      if (e.state && e.state.view) {
        setView(e.state.view);
      } else {
        setView('dashboard');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    // 3. Push to history when view changes manually
    if (window.history.state?.view !== view) {
      window.history.pushState({ view }, '');
    }

    // Existing scroll reset logic
    setTimeout(() => {
      window.scrollTo(0, 0);
      if (editorRef.current) editorRef.current.scrollTop = 0;
    }, 50);

    if (view === 'dashboard') {
      fetchSavedDecks();
    }
  }, [view]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (view === 'editor') searchDb(dbSearchTerm, typeFilter);
    }, 400);
    return () => clearTimeout(timer);
  }, [dbSearchTerm, typeFilter, view]);

  // --- Logic ---

  const fetchSavedDecks = async () => {
    if (!token) return;
    try {
      const res = await axios.get(`${API_URL}/decks`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSavedDecks(res.data);
    } catch (err) {
      console.error(err);
      if (err.response?.status === 401) handleLogout();
    }
  };

  useEffect(() => {
    if (token) {
      fetchSavedDecks();
    } else {
      setSavedDecks([]);
    }
  }, [token]);

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setSavedDecks([]);
    setDeck({ name: 'Nuevo Mazo', main: [], extra: [], side: [] });
    localStorage.removeItem('token');
  };

  const createNewDeck = () => {
    setDeck({ name: 'Nuevo Mazo', main: [], extra: [], side: [] });
    setSelectedCard(null);
    setView('editor');
  };

  const openDeck = async (deckName) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/decks/${encodeURIComponent(deckName)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeck(res.data);
      setSelectedCard(null);
      setView('editor');
    } catch (err) { 
      console.error(err); 
      if (err.response?.status === 401) handleLogout();
    } finally { setLoading(false); }
  };

  const deleteDeck = async (name) => {
    if (window.confirm(`¿Seguro que quieres borrar "${name}"?`)) {
      try {
        await axios.delete(`${API_URL}/decks/${encodeURIComponent(name)}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        fetchSavedDecks();
      } catch (err) { 
        console.error(err); 
        if (err.response?.status === 401) handleLogout();
      }
    }
  };

  const renameDeck = async (oldName) => {
    const newName = window.prompt("Nuevo nombre para el mazo:", oldName);
    if (newName && newName !== oldName) {
      try {
        await axios.patch(`${API_URL}/decks/${encodeURIComponent(oldName)}`, 
          { name: newName },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        fetchSavedDecks();
      } catch (err) { 
        console.error(err); 
        if (err.response?.status === 401) handleLogout();
      }
    }
  };

  const saveDeckToBackend = async () => {
    if (!deck.name || deck.name === 'Nuevo Mazo') {
      const newName = window.prompt("Por favor, ponle un nombre al mazo:", deck.name);
      if (!newName) return;
      setDeck(prev => ({ ...prev, name: newName }));
      deck.name = newName;
    }

    // Check if name already exists (excluding the current one if we were editing it)
    // Actually, since we don't have stable IDs, any same name will trigger this.
    const exists = savedDecks.some(d => d.name === deck.name);
    if (exists) {
      if (!window.confirm(`Ya existe un mazo llamado "${deck.name}". ¿Quieres sobreescribirlo?`)) {
        return;
      }
    }

    try {
      const payload = {
        name: deck.name,
        main: deck.main.map(c => c.name),
        extra: deck.extra.map(c => c.name),
        side: deck.side.map(c => c.name)
      };
      await axios.post(`${API_URL}/save-deck`, payload, {
        headers: { Authorization: `Bearer ${token}` }
      });

      await fetchSavedDecks();
      alert(`¡Mazo "${deck.name}" guardado correctamente!`);
    } catch (err) {
      console.error(err);
      alert("Error al guardar el mazo.");
    }
  };

  const searchDb = async (q, type) => {
    try {
      const res = await axios.get(`${API_URL}/cards?q=${q}`);
      let data = res.data.data || [];
      if (type !== 'All') data = data.filter(c => c.type.toLowerCase().includes(type.toLowerCase()));
      setDbResults(data);
    } catch (err) { console.error(err); }
  };

  const sendMessage = async () => {
    if (!input.trim()) return;
    const newMsg = { text: input, type: 'user' };
    setMessages(prev => ({ ...prev, [activeTab]: [...prev[activeTab], newMsg] }));
    setInput('');
    setLoading(true);
    try {
      const res = await axios.post(`${API_URL}/chat`, 
        { message: input },
        { headers: { Authorization: `Bearer ${token}`, 'x-session-id': 'default' } }
      );
      const { response, deck_data } = res.data;
      if (deck_data) setDeck(deck_data);
      setMessages(prev => ({ ...prev, [activeTab]: [...prev[activeTab], { text: response, type: 'ai' }] }));
    } catch (err) { 
      console.error(err);
      const errorMsg = "Lo siento, hubo un error al procesar tu mensaje. ¿Está Ollama encendido?";
      setMessages(prev => ({ ...prev, [activeTab]: [...prev[activeTab], { text: errorMsg, type: 'ai' }] }));
      if (err.response?.status === 401) handleLogout();
    } finally { setLoading(false); }
  };

  const addCardToDeck = (card) => {
    const allCards = [...deck.main, ...deck.extra, ...deck.side];
    if (allCards.filter(c => c.name === card.name).length >= 3) return;
    const cardData = { ...card, image: card.card_images[0].image_url_small };
    const isExtra = /fusion|synchro|xyz|link/i.test(card.type);
    if (isExtra) {
      if (deck.extra.length < 15) setDeck(prev => ({ ...prev, extra: [...prev.extra, cardData] }));
    } else {
      if (deck.main.length < 60) setDeck(prev => ({ ...prev, main: [...prev.main, cardData] }));
    }
  };

  const removeCard = (index, section) => {
    setDeck(prev => ({ ...prev, [section]: prev[section].filter((_, i) => i !== index) }));
  };

  const clearDeck = () => {
    if (window.confirm("¿Estás seguro de que quieres borrar todo el mazo?")) {
      setDeck({ name: 'Nuevo Mazo', main: [], extra: [], side: [] });
    }
  };

  const handleDragStart = (e, card, index = null, section = null) => {
    e.dataTransfer.setData('card', JSON.stringify(card));
    if (index !== null) {
      e.dataTransfer.setData('sourceIndex', index);
      e.dataTransfer.setData('sourceSection', section);
    }
  };

  const handleDropToSection = (e, targetSection) => {
    e.preventDefault();
    const cardDataString = e.dataTransfer.getData('card');
    if (!cardDataString) return;
    const cardData = JSON.parse(cardDataString);
    const isExtra = /fusion|synchro|xyz|link/i.test(cardData.type);
    if (targetSection === 'extra' && !isExtra) return;
    if (targetSection === 'main' && isExtra) return;
    const sourceIndex = e.dataTransfer.getData('sourceIndex');
    const sourceSection = e.dataTransfer.getData('sourceSection');
    if (sourceIndex === "") {
      const allCards = [...deck.main, ...deck.extra, ...deck.side];
      if (allCards.filter(c => c.name === cardData.name).length >= 3) return;
    }
    if (sourceIndex !== "") {
      const idx = parseInt(sourceIndex);
      if (sourceSection === targetSection) return;
      const newCard = { ...deck[sourceSection][idx] };
      setDeck(prev => {
        const sourceList = prev[sourceSection].filter((_, i) => i !== idx);
        const targetList = [...prev[targetSection], newCard];
        return { ...prev, [sourceSection]: sourceList, [targetSection]: targetList };
      });
    } else {
      const formattedCard = { ...cardData, image: cardData.card_images[0].image_url_small };
      setDeck(prev => ({ ...prev, [targetSection]: [...prev[targetSection], formattedCard] }));
    }
  };

  const handleDropToRemove = (e) => {
    e.preventDefault();
    const index = e.dataTransfer.getData('sourceIndex');
    const section = e.dataTransfer.getData('sourceSection');
    if (index !== "" && section) removeCard(parseInt(index), section);
  };

  const handleDragChatStart = (e) => { setIsDragging(true); setDragOffset({ x: e.clientX - chatPos.x, y: e.clientY - chatPos.y }); };
  const handleToggleMouseDown = (e) => { toggleDidMove.current = false; setIsToggleDragging(true); setToggleDragOffset({ x: e.clientX - togglePos.x, y: e.clientY - togglePos.y }); };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (isDragging) setChatPos({ x: e.clientX - dragOffset.x, y: e.clientY - dragOffset.y });
      if (isToggleDragging) { toggleDidMove.current = true; setTogglePos({ x: e.clientX - toggleDragOffset.x, y: e.clientY - toggleDragOffset.y }); }
    };
    const handleMouseUp = () => { setIsDragging(false); setIsToggleDragging(false); };
    if (isDragging || isToggleDragging) { window.addEventListener('mousemove', handleMouseMove); window.addEventListener('mouseup', handleMouseUp); }
    return () => { window.removeEventListener('mousemove', handleMouseMove); window.removeEventListener('mouseup', handleMouseUp); };
  }, [isDragging, dragOffset, isToggleDragging, toggleDragOffset]);

  function renderFloatingChat() {
    return (
      <>
        {isChatOpen && (
          <div className="floating-chat" style={{ left: chatPos.x, top: chatPos.y }}>
            <div className="chat-handle" onMouseDown={handleDragChatStart}>
              <div className="handle-title">AI Assistant</div>
              <button className="close-chat" onClick={() => setIsChatOpen(false)}><X size={16} /></button>
            </div>
            <div className="chat-messages">
              {messages[activeTab].map((msg, i) => (<div key={i} className={`message ${msg.type}`}>{msg.text}</div>))}
              {loading && <div className="message ai">...</div>}
            </div>
            <div className="chat-input-area">
              <input value={input} onChange={(e) => setInput(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && sendMessage()} placeholder="Pregunta algo..." />
              <button className="send-btn" onClick={sendMessage}><Send size={18} /></button>
            </div>
          </div>
        )}
        <button className="floating-toggle" style={{ left: togglePos.x, top: togglePos.y, bottom: 'auto' }} onMouseDown={handleToggleMouseDown} onClick={() => { if (!toggleDidMove.current) setIsChatOpen(!isChatOpen); }}>
          <span className="dots">...</span>
        </button>
      </>
    );
  }

  if (!token) {
    return <Login onLogin={(t) => {
      setToken(t);
      localStorage.setItem('token', t);
    }} />;
  }

  return (
    <>
      <div className="dashboard-container">
        <div className="dashboard-sticky-header">
          <div className="dashboard-header">
            <h1>YU-GI-OH HELPER</h1>
            <button className="logout-btn" onClick={handleLogout} title="Cerrar Sesión">
              <LogOut size={20} />
            </button>
          </div>

          <div className="dashboard-search-bar">
            <Search size={20} color="#888" />
            <input
              type="text"
              placeholder="Buscar entre tus mazos..."
              value={dashboardSearch}
              onChange={(e) => setDashboardSearch(e.target.value)}
            />
          </div>

          <div className="dashboard-actions">
            <div className="dash-action-card" onClick={createNewDeck}>
              <Plus size={22} style={{ color: 'var(--accent)' }} />
              <div>NUEVO MAZO</div>
            </div>
            <div className="dash-action-card">
              <Book size={22} style={{ color: '#2196f3' }} />
              <div>Upload Deck</div>
            </div>
            <div className="dash-action-card">
              <Swords size={22} style={{ color: '#ff9800' }} />
              <div>DUELO IA</div>
            </div>
          </div>
        </div>

        <div className="view-controls">
          <button className={`view-btn ${viewMode === 'grid' ? 'active' : ''}`} onClick={() => setViewMode('grid')}><LayoutGrid size={18} /></button>
          <button className={`view-btn ${viewMode === 'list' ? 'active' : ''}`} onClick={() => setViewMode('list')}><List size={18} /></button>
        </div>

        <div className="decks-grid">
          {savedDecks.filter(d => d.name.toLowerCase().includes(dashboardSearch.toLowerCase())).map((d, i) => (
            <div key={i} className="deck-card" style={{ backgroundImage: d.image ? `url(${d.image})` : 'none' }} onClick={() => openDeck(d.name)}>
              <div className="deck-card-overlay">
                <div>
                  <div className="deck-card-name">{d.name}</div>
                  <div className="deck-card-stats">
                    <span>Main {d.main.length}</span>
                    <span>Extra {d.extra.length}</span>
                    <span>Side {d.side.length}</span>
                  </div>
                </div>
                <div className="deck-card-actions">
                  <button className="deck-card-action-btn" onClick={(e) => { e.stopPropagation(); renameDeck(d.name); }}><Edit2 size={16} /></button>
                  <button className="deck-card-action-btn"><Copy size={16} /></button>
                  <button className="deck-card-action-btn delete" onClick={(e) => { e.stopPropagation(); deleteDeck(d.name); }}><Trash2 size={16} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {view === 'editor' && (
        <div className="app-container" onDrop={handleDropToRemove} onDragOver={(e) => e.preventDefault()}>
          <div className="sidebar info-sidebar">
            <button className="back-btn" onClick={() => setView('dashboard')}><ArrowLeft size={16} /> Dashboard</button>
            {selectedCard ? (
              <div className="card-preview-new">
                <div className="preview-name-pill">{selectedCard.name}</div>
                <div className="preview-img-wrap"><img src={selectedCard.card_images?.[0]?.image_url || selectedCard.image} alt={selectedCard.name} className="preview-img-large" /></div>
                <div className="preview-info-card">
                  <div className="info-id-row"><span className="info-card-id">{selectedCard.id}</span><span className="info-tcg-tag">(TCG/OCG)</span></div>
                  <div className="info-type-row">[{selectedCard.type?.includes('Monster') ? `${selectedCard.type.replace(/ Monster$/, '')}|Effect` : selectedCard.type}] {selectedCard.race}/{selectedCard.attribute || ''}</div>
                  {selectedCard.type?.includes('Monster') && <div className="info-stats-row">[★{selectedCard.level || selectedCard.rank || 0}] {selectedCard.atk}/{selectedCard.def}</div>}
                  <div className="info-desc-full">{selectedCard.desc}</div>
                </div>
              </div>
            ) : (
              <div className="empty-info"><Info size={48} style={{ marginBottom: '1rem', opacity: 0.3 }} /><p>Selecciona una carta para ver sus detalles</p></div>
            )}
          </div>

          <div className="editor-main" ref={editorRef} onDragOver={(e) => e.preventDefault()}>
            <div className="deck-construction-header">
              <div className="header-left">
                <input
                  className="deck-title-main"
                  value={deck.name}
                  onChange={(e) => setDeck(prev => ({ ...prev, name: e.target.value }))}
                  style={{ background: 'transparent', border: 'none', color: 'white', fontStyle: 'italic', width: '100%', outline: 'none' }}
                />
                <div className="regulation-tag">REGULATION: <span className="tag-box">TCG/OCG Unlimited</span></div>
              </div>
              <div className="header-actions">
                <button className="action-btn-danger" onClick={clearDeck}><Trash2 size={16} /> CLEAR</button>
                <button className="action-btn-text" onClick={saveDeckToBackend}><Save size={16} /> SAVE</button>
                <button className="action-btn-filled"><Plus size={16} /> IMPORT</button>
              </div>
            </div>

            <div className="stats-panels">
              <div className="stats-card main-stats"><span className="stats-label">MAIN</span><div className="stats-count"><span className="count-num">{deck.main.length}</span></div></div>
              <div className="stats-card extra-stats"><span className="stats-label">EXTRA</span><div className="stats-count"><span className="count-num">{deck.extra.length}</span></div></div>
              <div className="stats-card side-stats"><span className="stats-label">SIDE</span><div className="stats-count"><span className="count-num">{deck.side.length}</span></div></div>
            </div>

            <div className="deck-sections">
              {['main', 'extra', 'side'].map(section => (
                <section key={section} className="deck-section">
                  <h2 className={`deck-section-title ${section}-title`}>{section.toUpperCase()} DECK</h2>
                  <div className="deck-grid" onDrop={(e) => handleDropToSection(e, section)} onDragOver={(e) => e.preventDefault()}>
                    {deck[section].map((card, i) => (
                      <div key={i} className="card-item" draggable onDragStart={(e) => handleDragStart(e, card, i, section)} onContextMenu={(e) => { e.preventDefault(); removeCard(i, section); }}>
                        <div className="card-img" onClick={() => setSelectedCard(card)}><img src={card.image} alt="card" /></div>
                      </div>
                    ))}
                    {[...Array(Math.max(0, (section === 'main' ? 10 : 5) - deck[section].length))].map((_, i) => (
                      <div key={`empty-${section}-${i}`} className="card-item empty-slot"><Plus size={20} /></div>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </div>

          <div className="db-sidebar">
            <div className="db-header">
              <input type="text" placeholder="Buscar carta..." value={dbSearchTerm} onChange={(e) => setDbSearchTerm(e.target.value)} />
              <div className="filter-group">
                {['All', 'Monster', 'Spell', 'Trap'].map(t => (
                  <button key={t} className={`filter-btn ${typeFilter === t ? 'active' : ''}`} onClick={() => setTypeFilter(t)}>{t}</button>
                ))}
              </div>
            </div>
            <div className="db-results">
              {dbResults.slice(0, displayLimit === 'All' ? undefined : displayLimit).map(card => (
                <div key={card.id} className={`db-card-row ${selectedCard?.id === card.id ? 'selected' : ''}`} draggable onDragStart={(e) => handleDragStart(e, card)} onClick={() => setSelectedCard(card)} onContextMenu={(e) => { e.preventDefault(); addCardToDeck(card); }}>
                  <img src={card.card_images[0].image_url_small} alt="c" />
                  <div className="db-card-info">
                    <div className="name">{card.name}</div>
                    <div className="type">{card.type}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      {renderFloatingChat()}
    </>
  );
}

export default App;
