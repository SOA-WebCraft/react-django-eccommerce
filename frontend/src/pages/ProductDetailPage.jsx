import { useEffect, useState } from 'react';
import { FiEdit2, FiHeart, FiShoppingCart, FiTrash2 } from 'react-icons/fi';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { catalogApi } from '../api/services';
import { ApiError } from '../api/client';
import { ProductCard } from '../components/ProductCard';
import { ProductRating, RatingInput } from '../components/ProductRating';
import { ProductPrice } from '../components/ProductPrice';
import { Alert, Button, EmptyState, Loader, QuantityControl } from '../components/ui';
import { useAuth } from '../hooks/useAuth';
import { useCart } from '../hooks/useCart';
import { useToast } from '../hooks/useToast';
import { useWishlist } from '../hooks/useWishlist';
import { formatPrice } from '../utils/format';
import { productPath } from '../utils/productPath';
export function ProductDetailPage() {
    const { slug = '' } = useParams();
    const navigate = useNavigate();
    const { isAuthenticated, user } = useAuth();
    const { cart, add, adjust } = useCart();
    const { notify } = useToast();
    const { has: isWishlisted, toggle: toggleWishlistItem } = useWishlist();
    const [product, setProduct] = useState(null);
    const [related, setRelated] = useState([]);
    const [selectedImage, setSelectedImage] = useState('');
    const [loading, setLoading] = useState(true);
    const [adding, setAdding] = useState(false);
    const [error, setError] = useState('');
    const [reviews, setReviews] = useState({ count: 0, next: null, previous: null, results: [] });
    const [reviewPage, setReviewPage] = useState(1);
    const [reviewError, setReviewError] = useState('');
    const [reviewing, setReviewing] = useState(false);
    const [savingReview, setSavingReview] = useState(false);
    const [savingWishlist, setSavingWishlist] = useState(false);
    const [reviewForm, setReviewForm] = useState({ rating: 5, title: '', comment: '' });
    useEffect(() => {
        setLoading(true);
        catalogApi.product(slug)
            .then(async (data) => {
            setProduct(data);
            setSelectedImage(data.image || data.gallery_images[0]?.image || '');
            const result = await catalogApi.products({ category: data.category_name.toLowerCase().replaceAll(' ', '-') });
            setRelated(result.results.filter((item) => item.id !== data.id).slice(0, 4));
        })
            .catch((reason) => setError(reason.message))
            .finally(() => setLoading(false));
    }, [slug]);
    useEffect(() => {
        catalogApi.reviews(slug, reviewPage)
            .then((data) => {
            setReviews(data);
            setReviewError('');
        })
            .catch((reason) => setReviewError(reason.message));
    }, [slug, reviewPage]);
    const cartItem = product
        ? cart?.items.find((item) => item.product === product.id)
        : undefined;
    if (loading)
        return <div className="container page"><Loader label="Loading product"/></div>;
    if (error || !product)
        return <div className="container page"><Alert>{error || 'Product not found.'}</Alert><Link to="/products">Return to products</Link></div>;
    const images = [product.image, ...product.gallery_images.map((item) => item.image)].filter(Boolean);
    const sections = product.description.split(/\n\n+/);
    const ownReview = reviews.results.find((review) => review.customer.id === user?.id);
    const addToCart = async () => {
        if (!isAuthenticated) {
            navigate('/login', { state: { from: productPath(product) } });
            return;
        }
        setAdding(true);
        try {
            await add(product.id, 1);
            notify(`${product.name} added to your bag.`, 'success');
        }
        catch (reason) {
            if (!(reason instanceof ApiError)) {
                notify(reason instanceof Error ? reason.message : 'Unable to add product.', 'error');
            }
        }
        finally {
            setAdding(false);
        }
    };
    const changeQuantity = async (operation) => {
        setAdding(true);
        try {
            await adjust(cartItem.id, operation);
        }
        catch (reason) {
            if (!(reason instanceof ApiError)) {
                notify(reason instanceof Error ? reason.message : 'Unable to update cart quantity.', 'error');
            }
        }
        finally {
            setAdding(false);
        }
    };
    const refreshReviewsAndRating = async () => {
        const [reviewData, productData] = await Promise.all([
            catalogApi.reviews(slug, reviewPage),
            catalogApi.product(slug),
        ]);
        setReviews(reviewData);
        setProduct(productData);
    };
    const beginEditingReview = (review) => {
        setReviewForm({
            rating: review.rating,
            title: review.title,
            comment: review.comment,
        });
        setReviewing(true);
    };
    const submitReview = async (event) => {
        event.preventDefault();
        if (!reviewForm.title.trim() || !reviewForm.comment.trim()) {
            setReviewError('Add both a title and review comment.');
            return;
        }
        setSavingReview(true);
        setReviewError('');
        try {
            if (ownReview)
                await catalogApi.updateReview(slug, ownReview.id, reviewForm);
            else
                await catalogApi.createReview(slug, reviewForm);
            await refreshReviewsAndRating();
            setReviewing(false);
            setReviewForm({ rating: 5, title: '', comment: '' });
            notify(ownReview ? 'Your review was updated.' : 'Thanks for reviewing this product.', 'success');
        }
        catch (reason) {
            setReviewError(reason.message);
        }
        finally {
            setSavingReview(false);
        }
    };
    const deleteReview = async (review) => {
        if (!window.confirm('Delete your product review?'))
            return;
        setSavingReview(true);
        try {
            await catalogApi.deleteReview(slug, review.id);
            await refreshReviewsAndRating();
            setReviewing(false);
            notify('Your review was deleted.', 'success');
        }
        catch (reason) {
            setReviewError(reason.message);
        }
        finally {
            setSavingReview(false);
        }
    };
    const toggleWishlist = async () => {
        if (!isAuthenticated) {
            navigate('/login', { state: { from: productPath(product) } });
            return;
        }
        setSavingWishlist(true);
        try {
            const added = await toggleWishlistItem(product.id);
            notify(added ? `${product.name} saved to your wishlist.` : `${product.name} removed from your wishlist.`, 'success');
        }
        catch (reason) {
            if (!(reason instanceof ApiError))
                notify(reason instanceof Error ? reason.message : 'Unable to update your wishlist.', 'error');
        }
        finally {
            setSavingWishlist(false);
        }
    };
    return (<div className="container page product-detail-page">
      <nav className="breadcrumbs" aria-label="Breadcrumb"><Link to="/">Home</Link><span>/</span><Link to="/products">Products</Link><span>/</span><span>{product.name}</span></nav>
      <article className="product-detail">
        <div className="gallery">
          <div className="gallery__main">{selectedImage ? <img src={selectedImage} alt={product.name}/> : <span>ECCO</span>}</div>
          {images.length > 1 && <div className="gallery__thumbs">{images.map((image, index) => <button key={image} className={selectedImage === image ? 'is-active' : ''} onClick={() => setSelectedImage(image)} aria-label={`View image ${index + 1}`}><img src={image} alt=""/></button>)}</div>}
        </div>
        <div className="product-info">
          <p className="eyebrow">{product.category_name}</p><h1>{product.name}</h1>
          <ProductRating value={product.rating_average} count={product.review_count}/>
          <ProductPrice product={product} detail/>
          <div className={`stock ${product.stock_quantity ? 'stock--in' : 'stock--out'}`}><span />{product.stock_quantity ? `${product.stock_quantity} in stock` : 'Out of stock'}</div>
          <div className="description">{sections.map((section, index) => {
            const [heading, ...body] = section.split('\n');
            return body.length ? <section key={heading}><h2>{heading}</h2><p>{body.join(' ')}</p></section> : <p key={index}>{heading}</p>;
        })}</div>
          <div className="purchase-panel">
            {cartItem && <QuantityControl value={cartItem.quantity} max={Math.max(1, product.stock_quantity)} onDecrease={() => void changeQuantity('decrement')} onIncrease={() => void changeQuantity('increment')} disabled={!product.stock_quantity || adding}/>}
            {!cartItem && <Button className="add-to-cart-button" onClick={addToCart} disabled={!product.stock_quantity || adding}>{!adding && <FiShoppingCart aria-hidden="true"/>}{adding ? 'Adding…' : 'Add to cart'}</Button>}
            <Button variant="secondary" className={`wishlist-detail-button${isWishlisted(product.id) ? ' is-saved' : ''}`} onClick={() => void toggleWishlist()} disabled={savingWishlist} aria-pressed={isWishlisted(product.id)}><FiHeart aria-hidden="true"/>{isWishlisted(product.id) ? 'Saved' : 'Save'}</Button>
          </div>
          <p className="purchase-note">Inventory and total are validated securely when your order is placed.</p>
        </div>
      </article>
      <section className="product-reviews section" aria-labelledby="product-reviews-heading">
        <div className="section-heading product-reviews__heading"><div><p className="eyebrow">Verified buyers</p><h2 id="product-reviews-heading">Customer reviews</h2><ProductRating value={product.rating_average} count={product.review_count}/></div>{isAuthenticated && !reviewing && <Button onClick={() => ownReview ? beginEditingReview(ownReview) : setReviewing(true)}>{ownReview ? 'Edit your review' : 'Write a review'}</Button>}</div>
        {!isAuthenticated && <p className="review-signin-note"><Link to="/login" state={{ from: productPath(product) }}>Sign in</Link> to review a product you purchased.</p>}
        {reviewError && <Alert>{reviewError}</Alert>}
        {reviewing && <form className="review-form" onSubmit={submitReview}>
          <RatingInput value={reviewForm.rating} onChange={(rating) => setReviewForm((current) => ({ ...current, rating }))} disabled={savingReview}/>
          <label className="field"><span>Review title</span><input value={reviewForm.title} maxLength={120} onChange={(event) => setReviewForm((current) => ({ ...current, title: event.target.value }))} required/></label>
          <label className="field"><span>Your review</span><textarea value={reviewForm.comment} maxLength={2000} rows={5} onChange={(event) => setReviewForm((current) => ({ ...current, comment: event.target.value }))} required/></label>
          <div className="review-form__actions"><Button type="button" variant="secondary" onClick={() => setReviewing(false)} disabled={savingReview}>Cancel</Button><Button type="submit" disabled={savingReview}>{savingReview ? 'Saving...' : ownReview ? 'Update review' : 'Publish review'}</Button></div>
          <small>Only customers with a paid purchase can publish a review.</small>
        </form>}
        {reviews.results.length ? <div className="review-list">{reviews.results.map((review) => <article className="review-card" key={review.id}><header><div><ProductRating value={review.rating}/><h3>{review.title}</h3></div>{review.customer.id === user?.id && <div className="review-card__actions"><button onClick={() => beginEditingReview(review)} aria-label="Edit your review"><FiEdit2/></button><button onClick={() => void deleteReview(review)} aria-label="Delete your review" disabled={savingReview}><FiTrash2/></button></div>}</header><p>{review.comment}</p><footer><strong>{review.customer.name}</strong><span>Verified purchase</span><time dateTime={review.created_at}>{new Date(review.created_at).toLocaleDateString()}</time></footer></article>)}</div> : !reviewing && <EmptyState title="No reviews yet">Be the first verified buyer to review this product.</EmptyState>}
        {(reviews.previous || reviews.next) && <nav className="pagination" aria-label="Review pages"><Button variant="secondary" disabled={!reviews.previous} onClick={() => setReviewPage((page) => Math.max(1, page - 1))}>Previous</Button><span>Page {reviewPage}</span><Button variant="secondary" disabled={!reviews.next} onClick={() => setReviewPage((page) => page + 1)}>Next</Button></nav>}
      </section>
      {related.length > 0 && <section className="section"><div className="section-heading"><div><p className="eyebrow">Keep exploring</p><h2>Related products</h2></div></div><div className="product-grid product-grid--four">{related.map((item) => <ProductCard key={item.id} product={item}/>)}</div></section>}
    </div>);
}
