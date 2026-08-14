export function ProductRating({ value = 0, count, compact = false }) {
    const rating = Number(value) || 0;
    return <span className={`product-rating${compact ? ' product-rating--compact' : ''}`} aria-label={`${rating.toFixed(1)} out of 5 stars${count === undefined ? '' : ` from ${count} reviews`}`}>
      <span className="product-rating__stars" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((star) => <span key={star} className={rating >= star - 0.25 ? 'is-filled' : ''}>&#9733;</span>)}
      </span>
      <strong>{rating.toFixed(1)}</strong>
      {count !== undefined && <small>({count})</small>}
    </span>;
}

export function RatingInput({ value, onChange, disabled = false }) {
    return <fieldset className="rating-input">
      <legend>Rating</legend>
      <div>{[1, 2, 3, 4, 5].map((star) => <button key={star} type="button" className={star <= value ? 'is-selected' : ''} onClick={() => onChange(star)} disabled={disabled} aria-label={`${star} star${star === 1 ? '' : 's'}`} aria-pressed={star === value}>&#9733;</button>)}</div>
    </fieldset>;
}
