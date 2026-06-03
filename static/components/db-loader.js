class DBSyncLoader extends HTMLElement {
  connectedCallback() {
    this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = `
      <style>
        .sync-container {
          position: fixed;
          bottom: 20px;
          right: 20px;
          background: rgba(0, 0, 0, 0.8);
          padding: 10px 15px;
          border-radius: 5px;
          display: flex;
          align-items: center;
          gap: 10px;
          z-index: 1000;
        }
        .sync-button {
          background: #87CEEB;
          color: black;
          border: none;
          padding: 5px 10px;
          border-radius: 3px;
          cursor: pointer;
        }
        .sync-progress {
          font-size: 0.8em;
          color: #C0C0C0;
        }
        .status-indicator {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: #555;
        }
        .status-indicator.active {
          background: #0f0;
        }
      </style>
      <div class="sync-container">
        <div class="status-indicator"></div>
        <span class="sync-progress">DB Sync</span>
        <button class="sync-button">Sync Now</button>
      </div>
    `;

    this.shadowRoot.querySelector('.sync-button').addEventListener('click', () => this.syncData());
    this.checkSyncStatus();
  }

  async checkSyncStatus() {
    const indicator = this.shadowRoot.querySelector('.status-indicator');
    try {
      const response = await fetch('/api/sync-status');
      const data = await response.json();
      indicator.classList.toggle('active', data.isSynced);
      this.shadowRoot.querySelector('.sync-progress').textContent = 
        data.isSynced ? 'DB Synced' : 'Sync Required';
    } catch (error) {
      console.error('Error checking sync status:', error);
    }
  }

  async syncData() {
    const button = this.shadowRoot.querySelector('.sync-button');
    const progress = this.shadowRoot.querySelector('.sync-progress');
    button.disabled = true;
    progress.textContent = 'Syncing...';

    try {
      const response = await fetch('/api/sync-db', { method: 'POST' });
      const data = await response.json();
      if (data.success) {
        progress.textContent = 'Sync Complete';
        this.checkSyncStatus();
      } else {
        progress.textContent = 'Sync Failed';
      }
    } catch (error) {
      console.error('Error syncing data:', error);
      progress.textContent = 'Sync Error';
    } finally {
      setTimeout(() => {
        button.disabled = false;
        progress.textContent = 'DB Sync';
      }, 3000);
    }
  }
}

customElements.define('db-sync-loader', DBSyncLoader);