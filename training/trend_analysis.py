import pandas as pd

class TrendAnalyzer:

    @staticmethod
    def prepare_city_timeseries(df, city):
        df = df.copy()
        df.rename(columns={df.columns[0]: 'City'}, inplace=True)

        city_df = df[df['City'] == city].iloc[:, 1:].T
        city_df.columns = ['Service_Level']
        city_df['Month_Index'] = range(len(city_df))
        city_df = city_df.dropna()

        return city_df

class CallCenterAnalyzer:

    @staticmethod
    def prepare_call_center_timeseries(df, queue_name):
        df = df.copy()

        # Filter specific queue
        df = df[df['Queue Group/Line of Business'] == queue_name]

        # Clean Month and Year
        df['Month'] = df['Month'].astype(str).str.strip()
        df['Year'] = df['Year'].astype(int)

        # Create proper datetime column
        df['Month_Year'] = pd.to_datetime(
            df['Month'] + " " + df['Year'].astype(str),
            format="%b %Y",
            errors='coerce'
        )

        # Drop rows where date parsing failed
        df = df.dropna(subset=['Month_Year'])

        # Sort chronologically
        df = df.sort_values('Month_Year')

        # Keep only relevant columns
        df = df[['Month_Year', 'Calls Handled', 'Average Wait Time (minutes)']]

        # Drop missing values in metrics
        df = df.dropna()

        return df