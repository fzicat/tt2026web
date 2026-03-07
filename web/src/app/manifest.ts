import { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
    return {
        name: 'TradeTools',
        short_name: 'TradeTools',
        description: 'Trading portfolio management application',
        start_url: '/',
        display: 'standalone',
        background_color: '#282828',
        theme_color: '#282828',
        icons: [
            {
                src: '/icon-512x512.png',
                sizes: 'any',
                type: 'image/png',
                purpose: 'any',
            },
        ],
    }
}
