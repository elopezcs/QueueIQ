import matplotlib.pyplot as plt
import seaborn as sns

class DSSCharts:

    @staticmethod
    def trend_line(X, y, predictions=None, title="Trend Analysis"):
        plt.figure(figsize=(8,4))
        plt.scatter(X, y, label="Actual")
        
        if predictions is not None:
            plt.plot(X, predictions, color='red', label="Forecast")

        plt.xlabel("Time")
        plt.ylabel("Service Level (%)")
        plt.title(title)
        plt.legend()
        plt.show()

    @staticmethod
    def service_level_heatmap(df, title="Service Level Heatmap", context=''):
        """
        df: DataFrame with City as first column and months as remaining columns
        """
        # Ensure City is index
        heatmap_df = df.set_index(df.columns[0])

        results_df = heatmap_df.describe().T
        results = {
            'Mean Service Level': results_df['mean'].mean(),
            'Median Service Level': results_df['50%'].median(),
            'Max Service Level': results_df['max'].max(),
            'Min Service Level': results_df['min'].min()
        }
        print("Model Evaluation Summary")
        print("------------------------")
        for k, v in results.items():
            print(f"{k}: {v:.2f}")

        plt.figure(figsize=(14, 8))
        sns.heatmap(
            heatmap_df,
            cmap="YlGnBu",
            linewidths=0.3,
            linecolor='gray',
            cbar_kws={'label': 'Service Level (%)'},
            annot=False
        )

        plt.title(title)
        plt.xlabel("Month")
        plt.ylabel("City")
        plt.tight_layout()
        plt.show()

    @staticmethod
    def call_center_trends(df):
        fig, ax1 = plt.subplots(figsize=(10, 5))

        # Calls handled (bar)
        ax1.bar(
            df['Month_Year'],
            df['Calls Handled'],
            alpha=0.6,
            label="Calls Handled"
        )
        ax1.set_ylabel("Calls Handled")

        # Wait time (line)
        ax2 = ax1.twinx()
        ax2.plot(
            df['Month_Year'],
            df['Average Wait Time (minutes)'],
            color='red',
            marker='o',
            label="Avg Wait Time (min)"
        )
        ax2.set_ylabel("Average Wait Time (minutes)")

        ax1.set_xlabel("Time")
        plt.title("Call Volume vs Average Wait Time")

        fig.autofmt_xdate()
        plt.show()