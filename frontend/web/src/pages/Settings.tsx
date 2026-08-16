import { usePreferences, TextSize } from '../context/PreferencesContext'
import Toggle from '../components/ui/Toggle'

export default function Settings() {
  const { preferences, updatePreferences } = usePreferences()

  return (
    <div className="space-y-6">
      {/* Header */}
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* Reduce Motion */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Motion Preferences</h2>
        <p className="text-sm text-gray-400 mb-6">
          Control animations and transitions throughout the dashboard.
        </p>

        <div className="flex items-center justify-between p-4 bg-gray-900 rounded-lg">
          <div>
            <div className="font-medium text-white">Reduce Motion</div>
            <div className="text-sm text-gray-400">Minimize or disable animations</div>
          </div>
          <Toggle
            checked={preferences.reduceMotion}
            onChange={() => updatePreferences({ reduceMotion: !preferences.reduceMotion })}
            label="Reduce motion"
          />
        </div>
      </div>

      {/* Text Size */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Text Size</h2>
        <p className="text-sm text-gray-400 mb-6">
          Adjust the base text size for improved readability.
        </p>

        <div className="space-y-3">
          {(['default', 'large', 'larger'] as TextSize[]).map((size) => (
            <button
              key={size}
              onClick={() => updatePreferences({ textSize: size })}
              className={`w-full p-4 rounded-lg border text-left transition-colors ${
                preferences.textSize === size
                  ? 'bg-blue-900/20 border-blue-500/30 text-blue-400'
                  : 'bg-gray-900 border-gray-700 text-gray-300 hover:bg-gray-800'
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium capitalize">{size}</div>
                  <div className="text-sm text-gray-400">
                    {size === 'default' && 'Standard text size (16px base)'}
                    {size === 'large' && 'Larger text size (18px base)'}
                    {size === 'larger' && 'Largest text size (20px base)'}
                  </div>
                </div>
                {preferences.textSize === size && (
                  <span className="text-blue-400">&#10003;</span>
                )}
              </div>
              <div
                className="mt-2 text-gray-400"
                style={{
                  fontSize: size === 'default' ? '16px' : size === 'large' ? '18px' : '20px',
                }}
              >
                Sample preview text
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* High Contrast */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Contrast</h2>
        <p className="text-sm text-gray-400 mb-6">
          Increase contrast between text and backgrounds for better visibility.
        </p>

        <div className="flex items-center justify-between p-4 bg-gray-900 rounded-lg">
          <div>
            <div className="font-medium text-white">High Contrast Mode</div>
            <div className="text-sm text-gray-400">Enhance text and UI element contrast</div>
          </div>
          <Toggle
            checked={preferences.highContrast}
            onChange={() => updatePreferences({ highContrast: !preferences.highContrast })}
            label="High contrast mode"
          />
        </div>
      </div>

      {/* Preview Note */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="flex items-start space-x-3">
          <span className="text-blue-400 text-xl flex-shrink-0">&#9432;</span>
          <div>
            <h3 className="text-sm font-medium text-white">Live Preview</h3>
            <p className="text-xs text-gray-400 mt-1">
              Changes are applied immediately and saved automatically. Navigate to other pages
              to see how preferences affect the entire dashboard.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
